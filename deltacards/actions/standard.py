import math
from typing import Any, ClassVar, Literal, TYPE_CHECKING

from deltacards.actions.base import (
    Action,
    ActionCall,
    ActionContext,
    ActionOutcome,
    Arg,
)
from deltacards.actions.results import *
from deltacards.dsl.selectors import ENEMY_MONSTERS
from deltacards.dsl.transforms import RANDOM
from deltacards.dsl.values import HP
from deltacards.engine.modifiers import HealQuery
from deltacards.model.cards import (
    Card,
    CardZone,
    CaughtCardData,
    Monster,
    Spell,
)
from deltacards.model.enchantments import Enchantment
from deltacards.model.entity import Entity
from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardStatusId,
    CardToggleableAbility,
    DamageKind,
    KillCause,
    PlayerId,
    Tribe,
)
from deltacards.model.player import Player
from deltacards.model.requests import (
    ChoiceResponse,
    ChooseEntityPrompt,
    PendingChoiceRequest,
)
from deltacards.model.slots import BoardSlot
from deltacards.model.snapshots import CardSnapshot
from deltacards.model.types import (
    EnchantmentRemovalReason,
    GoldSpendReason,
)

if TYPE_CHECKING:
    from deltacards.dsl.vars import StateVar, Var
    from deltacards.model.artifacts import Artifact


__all__ = (
    'Action', 'ActionContext',
    'SetVar', 'SetEntityState', 'Choose', 'Reveal',
    'Hit', 'Heal',
    'Kill', 'ReleaseMonsterDeathFinalization',
    'Buff',
    'Draw', 'DrawNext', 'Overdraw', 'TakeFatigueDamage',
    'AddKeyword', 'RemoveKeyword',
    'SetStatus', 'RemoveStatus',
    'Silence', 'Paralyze', 'RemoveNegativeEffects',
    'SetPlayerHP',
    'SetStats', 'SetBaseStats', 'SwapStats', 'HalveStats',
    'Move', 'SwapCards',
    'Summon', 'Play', 'Cast', 'RemoveCardFromStack', 'EmitPlayResults',
    'TriggerAbility', 'ToggleAbility',
    'Catch', 'ReleaseCaughtCard',
    'Erase', 'TransformCard',
    'Attack', 'CombatDamage', 'AttackAftermath', 'RefreshAttacks',
    'EarnGold', 'SpendGold', 'SetGold',
    'AddArtifact', 'ToggleArtifact', 'TransformArtifact', 'UpdateArtifactCounter',
    'Enchant', 'RemoveEnchantment', 'TransformEnchantment', 'UpdateEnchantmentCounter',
    'ScheduleEffect', 'ScheduleDelayEffect',
    'SkipNextTurn', 'AdvanceTurn', 'ResolveScheduledEffectsAction',
    'PlayerStartTurnAction', 'PlayerEndTurnAction',
)


CARD_EDITABLE_ZONES = (CardZone.INVALID, CardZone.STACK, CardZone.BOARD, CardZone.HAND, CardZone.DECK)


class SetVar(Action):
    var: Arg['Var'] = Arg(raw=True)  # raw=True prevents turning `var` into a value
    value: Arg[Any] = Arg(preserve_list=True)

    def execute(self, var: 'Var', value: Any, *, ctx: ActionContext, **kwargs):
        ctx.vars[var.name] = value
        return ActionOutcome(success=True)


class SetEntityState(Action):
    state_var: Arg['StateVar'] = Arg(raw=True)  # raw=True prevents turning `state_var` into a value
    value: Arg[Any] = Arg(preserve_list=True)

    def execute(self, state_var: 'StateVar', value: Any, *, ctx: ActionContext, **kwargs):
        state_var.set_value(entity=ctx.source, value=value)
        return ActionOutcome(success=True)


class Choose(Action):
    player: Arg['Player'] = Arg()
    options: Arg['list[Entity]'] = Arg(preserve_list=True)

    @staticmethod
    def _store_choices(ctx: ActionContext, options: list[Entity], chosen: list[Entity]) -> None:
        ctx.vars['_choice_selected'] = chosen
        ctx.vars['_choice_not_selected'] = [entity for entity in options if entity not in chosen]

    def execute(self, player: 'Player', options: 'list[Entity]', *, ctx: ActionContext, **kwargs):
        if len(options) == 0:
            return ActionOutcome(success=False)

        if ctx.env.get('_auto_choose', False):
            chosen = [ctx.game.rng.choice(options)]
            self._store_choices(ctx, options, chosen)
            return ActionOutcome(success=True)

        def _on_choose(response: ChoiceResponse):
            chosen = [entity for entity in options if entity.id in response.selected_option_ids]
            self._store_choices(ctx, options, chosen)

        pending_request = PendingChoiceRequest(
            request_id=ctx.game.alloc_request_id(),
            player_id=player.id,
            prompt=ChooseEntityPrompt(
                options=options,
            ),
            on_choose=_on_choose,
        )

        return ActionOutcome(
            success=True,
            pending_request=pending_request,
        )


class Reveal(Action):
    card: Arg['Card'] = Arg(many=True)

    def execute(self, card: 'Card', *, ctx: ActionContext, **kwargs):
        return ActionOutcome(
            success=True,
            results=(
                CardRevealedResult(
                    source_id=ctx.source.id,
                    card_id=card.id,
                    card=card.to_snapshot(),
                ),
            ),
        )


class Hit(Action):
    target: Arg['Monster | Player'] = Arg(many=True)
    damage: Arg[int] = Arg()
    kind: Arg[DamageKind | None] = Arg(default=None)

    primary_result_type: ClassVar[type[ActionResult] | None] = EntityDamagedResult

    def execute(self, target: 'Monster | Player', damage: int, kind: DamageKind | None, *, ctx: ActionContext, **kwargs):
        res = ctx.game.apply_damage(
            target=target,
            damage=damage,
            source=ctx.source,
            kind=kind,
        )

        return ActionOutcome(
            success=(res.prevented_by != 'invalid_target'),
            results=res.results,
            action_calls=res.extra_actions,
        )


class Heal(Action):
    target: Arg['Monster | Player'] = Arg(many=True)
    amount: Arg[int] = Arg()

    def execute(self, target: 'Monster | Player', amount: int, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, (Monster, Player)):
            return ActionOutcome(success=False)

        if isinstance(target, Monster) and target.zone is not CardZone.BOARD:
            return ActionOutcome(success=False)

        q = HealQuery(
            game=ctx.game,
            source=ctx.source,
            target=target,
            amount=amount,
        )
        final_amount = ctx.game.rules.heal(q)

        hp_recovered = target.heal(final_amount)

        return ActionOutcome(
            success=True,
            results=(
                EntityHealedResult(
                    source_id=ctx.source.id,
                    target_id=target.id,
                    target=target.to_snapshot(),
                    amount=hp_recovered,
                ),
            ),
            affected=[target],
        )


class Kill(Action):
    target: Arg['Monster | Player'] = Arg(many=True)
    killer: Arg['Entity | None'] = Arg(default=None)
    skip_check_death_prevented: Arg[bool] = Arg(default=False)
    cause: Arg[KillCause] = Arg(default=KillCause.DESTROY_EFFECT)

    def execute(
        self,
        target: 'Monster | Player',
        killer: 'Entity | None',
        skip_check_death_prevented: bool,
        cause: KillCause,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(target, (Monster, Player)):
            return ActionOutcome(success=False)

        if killer is None:
            killer = ctx.source

        if not skip_check_death_prevented:
            death_prevented, extra_actions = ctx.game.check_death_prevented(
                target,
                killer,
                cause=cause,
            )
            if death_prevented:
                return ActionOutcome(
                    success=False,
                    action_calls=extra_actions,
                )

        action_calls = []
        results = []

        if isinstance(target, Monster):
            if target.zone is not CardZone.BOARD:
                return ActionOutcome(success=False)

            death_slot = ctx.game.board_slot(target.controller_id, target.pos)

            if target.has_keyword(CardKeyword.KR):
                if (
                    isinstance(killer, Monster)
                    and killer.zone is CardZone.BOARD
                    and killer.hp > 0
                ):
                    buff_target = killer
                else:
                    buff_target = (ENEMY_MONSTERS & (HP > 0)) >> RANDOM(1)

                action_calls.append(
                    ActionCall(Buff(target=buff_target, attack=1, hp=1), source=target)
                )

            if target.has_keyword(CardKeyword.WANTED):
                action_calls.append(
                    ActionCall(
                        EarnGold(player=ctx.game.player(target.controller_id).opponent, amount=1),
                        source=target,
                    )
                )

            dust_effect = target.get_ability(Ability.DUST)
            if dust_effect is not None:
                ctx.game.hold_monster_death_finalization(target)

                action_calls.append(
                    ActionCall(
                        TriggerAbility(target=target, ability=Ability.DUST),
                        source=target,
                        env={'killer': killer, 'death_slot': death_slot},
                    )
                )

                action_calls.append(
                    ActionCall(
                        ReleaseMonsterDeathFinalization(target=target),
                        source=target,
                    )
                )

            results.append(
                MonsterKilledResult(
                    source_id=ctx.source.id,
                    monster_id=target.id,
                    monster=target.to_snapshot(),
                    killer_id=killer.id,
                    killer=killer.to_snapshot(),
                    cause=cause,
                )
            )

            if target.death_finalization_locks > 0:
                ctx.game.move_monster_to_pending_death_state(target)
            else:
                ctx.game.move_card(target, target.controller_id, CardZone.DUSTPILE)

        elif isinstance(target, Player):
            ctx.game.game_over = True
            ctx.game.dead_players.add(target.id)

            results.append(
                PlayerDefeatedResult(
                    source_id=ctx.source.id,
                    player_id=target.id,
                    player=target.to_snapshot(),
                    killer_id=killer.id,
                    killer=killer.to_snapshot(),
                )
            )

        else:
            raise TypeError(f"Target is of invalid type {type(target)}")

        return ActionOutcome(
            success=True,
            results=results,
            affected=[target],
            action_calls=action_calls,
        )


class ReleaseMonsterDeathFinalization(Action):
    target: Arg['Monster'] = Arg()

    def execute(self, target: Monster, *, ctx: ActionContext, **kwargs):
        ctx.game.release_monster_death_finalization(target)
        return ActionOutcome(success=True)


class Buff(Action):
    target: Arg['Card | Player'] = Arg(many=True)
    cost: Arg[int] = Arg(default=0)
    attack: Arg[int] = Arg(default=0)
    hp: Arg[int] = Arg(default=0)
    min_cost: Arg[int | None] = Arg(default=None)
    min_attack: Arg[int | None] = Arg(default=None)
    min_hp: Arg[int | None] = Arg(default=None)

    def execute(
        self,
        target: 'Card | Player',
        cost: int,
        attack: int,
        hp: int,
        min_cost: int | None,
        min_attack: int | None,
        min_hp: int | None,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(target, (Card, Player)):
            return ActionOutcome(success=False)

        action_calls = []

        if isinstance(target, Card) and target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        if isinstance(target, Monster):
            target.buff(cost, attack, hp, min_cost, min_attack, min_hp)
            if target.hp <= 0 and target.zone is CardZone.BOARD:
                action_calls.append(
                    ActionCall(
                        Kill(
                            target=target,
                            killer=ctx.source,
                            cause=KillCause.OTHER,
                        ),
                        source=ctx.source,
                    )
                )

        elif isinstance(target, Spell):
            target.buff(cost)

        elif isinstance(target, Player):
            assert cost == 0 and attack == 0
            target.buff(hp=hp)

            if target.hp <= 0:
                action_calls.append(
                    ActionCall(
                        Kill(
                            target=target,
                            killer=ctx.source,
                            cause=KillCause.OTHER,
                        ),
                        source=ctx.source,
                    )
                )

        return ActionOutcome(
            success=True,
            affected=[target],
            action_calls=action_calls,
        )


def perform_card_draw(player: 'Player', card: 'Card', reason: str, *, ctx: 'ActionContext') -> ActionOutcome:
    if card.zone is not CardZone.DECK or card.controller_id != player.id:
        return ActionOutcome(success=False)

    action_calls = []

    # Turbo: This card will trigger its effect when drawn (except during game start or mulligan).
    # Currently, cards drawn both during the game start and during the mulligan are added
    # without using this action, so this check is currently redundant, but is still here for clarity.
    if reason not in ('game_start', 'mulligan'):
        effect = card.get_ability(Ability.TURBO)
        if effect is not None:
            action_calls.append(ActionCall(TriggerAbility(target=card, ability=Ability.TURBO), source=card))

    if len(player.hand) >= 7:
        return ActionOutcome(
            success=True,
            action_calls=[ActionCall(Overdraw(player=player, card=card), source=ctx.source), *action_calls],
        )

    ctx.game.move_card(card, controller_id=player.id, zone=CardZone.HAND)

    return ActionOutcome(
        success=True,
        results=(
            CardDrawnResult(
                source_id=ctx.source.id,
                player_id=player.id,
                card_id=card.id,
                card=card.to_snapshot(),
                reason=reason,
            ),
        ),
        affected=[card],
        action_calls=action_calls,
    )


class Draw(Action):
    player: Arg['Player'] = Arg()
    card: Arg['Card'] = Arg(many=True)
    reason: Arg[str] = Arg(default='effect')

    def execute(self, player: 'Player', card: 'Card', reason: str, *, ctx: ActionContext, **kwargs):
        return perform_card_draw(player, card, reason, ctx=ctx)


class DrawNext(Action):
    player: Arg['Player'] = Arg(many=True)
    reason: Arg[str] = Arg(default='effect')
    from_pos: Arg[str] = Arg(default='top')

    def execute(self, player: 'Player', reason: str, from_pos: str, *, ctx: ActionContext, **kwargs):
        if from_pos == 'top':
            if len(player.deck) == 0:
                return ActionOutcome(
                    success=False,
                    action_calls=[ActionCall(TakeFatigueDamage(player=player), source=player)],
                )

            card = player.deck.cards[0]

        elif from_pos == 'bottom':
            if len(player.deck) == 0:
                return ActionOutcome(success=False)

            card = player.deck.cards[-1]

        else:
            raise ValueError(f"`from_pos` got invalid value: {from_pos}")

        return perform_card_draw(player, card, reason, ctx=ctx)


class Overdraw(Action):
    player: Arg['Player'] = Arg()
    card: Arg['Card'] = Arg(many=True)

    def execute(self, player: 'Player', card: 'Card', *, ctx: ActionContext, **kwargs):
        overdraw_prevented, extra_actions = ctx.game.check_overdraw_prevented(player)
        if overdraw_prevented:
            return ActionOutcome(success=False, action_calls=extra_actions)

        ctx.game.move_card(card, controller_id=player.id, zone=CardZone.ERASED)
        return ActionOutcome(
            success=True,
            results=(
                CardOverdrawnResult(
                    source_id=ctx.source.id,
                    player_id=player.id,
                    card_id=card.id,
                    card=card.to_snapshot(),
                ),
            ),
            affected=[card],
        )


class TakeFatigueDamage(Action):
    player: Arg['Player'] = Arg(many=True)

    def execute(self, player: 'Player', *, ctx: ActionContext, **kwargs):
        player.fatigue_counter += 1

        return ActionOutcome(
            success=True,
            action_calls=[
                ActionCall(
                    Hit(target=player, damage=player.fatigue_counter, kind=DamageKind.FATIGUE),
                    source=ctx.source,
                ),
            ],
        )


class AddKeyword(Action):
    target: Arg['Card'] = Arg(many=True)
    keyword: Arg[CardKeyword] = Arg()

    def execute(self, target: Card, keyword: CardKeyword, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        target.add_keyword(keyword)
        return ActionOutcome(success=True, affected=[target])


class RemoveKeyword(Action):
    target: Arg['Card'] = Arg(many=True)
    keyword: Arg[CardKeyword] = Arg()

    def execute(self, target: Card, keyword: CardKeyword, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        target.remove_keyword(keyword)
        return ActionOutcome(success=True, affected=[target])


class SetStatus(Action):
    target: Arg['Card'] = Arg(many=True)
    status_id: Arg[CardStatusId] = Arg()
    value: Arg[int] = Arg(default=1)

    def execute(self, target: Card, status_id: CardStatusId, value: int, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        target.set_status(status_id, value)
        return ActionOutcome(success=True, affected=[target])


class RemoveStatus(Action):
    target: Arg['Card'] = Arg(many=True)
    status_id: Arg[CardStatusId] = Arg()

    def execute(self, target: Card, status_id: CardStatusId, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        target.remove_status(status_id)
        return ActionOutcome(success=True, affected=[target])


class Silence(Action):
    target: Arg['Monster'] = Arg(many=True)

    def execute(self, target: Monster, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Monster):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        success = target.silence()
        return ActionOutcome(
            success=success,
            affected=[target] if success else [],
        )


class Paralyze(Action):
    target: Arg['Monster'] = Arg(many=True)

    def execute(self, target: Monster, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Monster):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        paralyzed_turns = target.get_status(CardStatusId.PARALYZED)
        if paralyzed_turns > 0:
            return ActionOutcome(success=False)

        target.set_status(CardStatusId.PARALYZED, 2)
        return ActionOutcome(success=True, affected=[target])


class RemoveNegativeEffects(Action):
    target: Arg['Monster'] = Arg(many=True)

    def execute(self, target: Monster, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Monster):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        target.remove_negative_effects()
        return ActionOutcome(
            success=True,
            affected=[target],
        )


class SetPlayerHP(Action):
    player: Arg['Player'] = Arg()
    hp: Arg[int] = Arg()

    def execute(self, player: 'Player', hp: int, *, ctx: ActionContext, **kwargs):
        if not isinstance(player, Player):
            return ActionOutcome(success=False)

        player.set_hp(hp)
        return ActionOutcome(success=True, affected=[player])


class SetStats(Action):
    target: Arg['Card'] = Arg(many=True)
    cost: Arg[int | None] = Arg(default=None)
    attack: Arg[int | None] = Arg(default=None)
    hp: Arg[int | None] = Arg(default=None)

    def execute(
        self,
        target: 'Card',
        cost: int | None,
        attack: int | None,
        hp: int | None,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        action_calls = []

        if attack is not None:
            assert isinstance(target, Monster)
            target.buff(attack=attack - (target.base.attack + target.buffs.attack))

        if hp is not None:
            assert isinstance(target, Monster)
            target.hp_missing = 0
            target.buff(hp=hp - (target.base.hp + target.buffs.max_hp))

            if target.hp <= 0 and target.zone is CardZone.BOARD:
                action_calls.append(
                    ActionCall(
                        Kill(
                            target=target,
                            killer=ctx.source,
                            cause=KillCause.OTHER,
                        ),
                        source=ctx.source,
                    )
                )

        if cost is not None:
            target.buff(cost=cost - (target.base.cost + target.buffs.cost))

        return ActionOutcome(
            success=True,
            affected=[target],
            action_calls=action_calls,
        )


class SetBaseStats(Action):
    target: Arg['Card'] = Arg(many=True)
    cost: Arg[int | None] = Arg(default=None)
    attack: Arg[int | None] = Arg(default=None)
    hp: Arg[int | None] = Arg(default=None)

    def execute(
        self,
        target: 'Card',
        cost: int | None,
        attack: int | None,
        hp: int | None,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        action_calls = []

        if isinstance(target, Monster):
            target.set_base_stats(cost=cost, attack=attack, hp=hp)

            if (hp is not None) and (target.hp <= 0) and (target.zone is CardZone.BOARD):
                action_calls.append(
                    ActionCall(
                        Kill(
                            target=target,
                            killer=ctx.source,
                            cause=KillCause.OTHER,
                        ),
                        source=ctx.source,
                    )
                )

        else:
            target.set_base_stats(cost=cost)

        return ActionOutcome(
            success=True,
            affected=[target],
            action_calls=action_calls,
        )


class SwapStats(Action):
    target: Arg['Monster'] = Arg(many=True)

    def execute(self, target: Monster, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        action_calls = []
        target.buff(attack=target.hp - target.attack, hp=target.attack - target.hp)

        if target.hp <= 0 and target.zone is CardZone.BOARD:
            action_calls.append(
                ActionCall(
                    Kill(
                        target=target,
                        killer=ctx.source,
                        cause=KillCause.OTHER,
                    ),
                    source=ctx.source,
                )
            )

        return ActionOutcome(
            success=True,
            affected=[target],
            action_calls=action_calls,
        )


class HalveStats(Action):
    target: Arg['Monster'] = Arg(many=True)
    round_up: Arg['bool'] = Arg()

    def execute(self, target: Monster, round_up: bool, *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        action_calls = []

        round_func = math.floor if round_up else math.ceil  # negative stat buffs are inverted
        target.buff(attack=-round_func(target.attack / 2), hp=-round_func(target.hp / 2))

        if target.hp <= 0 and target.zone is CardZone.BOARD:
            action_calls.append(
                ActionCall(
                    Kill(
                        target=target,
                        killer=ctx.source,
                        cause=KillCause.OTHER,
                    ),
                    source=ctx.source,
                )
            )

        return ActionOutcome(
            success=True,
            affected=[target],
            action_calls=action_calls,
        )


class Move(Action):
    target: Arg['Card'] = Arg(many=True)
    zone: Arg[CardZone] = Arg()
    controller: Arg['Player | None'] = Arg(default=None)
    pos: Arg['int | str | None'] = Arg(default=None)  # board/deck index, or one of: 'top', 'bottom', 'shuffle'

    def execute(self, target: 'Card', zone: CardZone, controller: 'Player | None', pos: 'int | str | None', *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        # Cards aren't allowed to be moved from ERASED zone
        if target.zone is CardZone.ERASED:
            return ActionOutcome(success=False)

        # Dustpile monsters can only be erased
        if target.zone is CardZone.DUSTPILE:
            return ActionOutcome(success=False)

        # Kill() should be used instead
        if zone is CardZone.DUSTPILE:
            return ActionOutcome(success=False)

        if controller is None:
            controller = ctx.game.players[target.controller_id]

        if zone == CardZone.HAND:
            if target.zone is CardZone.DECK and target.controller_id == controller.id:
                return ActionOutcome(
                    success=True,
                    action_calls=[ActionCall(Draw(player=controller, card=target), source=ctx.source)],
                )

            if len(controller.hand) >= 7:
                if target.zone is CardZone.BOARD:
                    return ActionOutcome(
                        success=True,
                        action_calls=[
                            ActionCall(
                                Kill(
                                    target=target,
                                    killer=ctx.source,
                                    cause=KillCause.OTHER,
                                ),
                                source=ctx.source,
                            )
                        ],
                    )
                elif target.zone is CardZone.DECK:
                    return ActionOutcome(
                        success=True,
                        action_calls=[ActionCall(Overdraw(player=controller, card=target), source=ctx.source)],
                    )
                else:
                    return ActionOutcome(success=False)

        ctx.game.move_card(card=target, controller_id=controller.id, zone=zone, pos=pos)
        return ActionOutcome(success=True, affected=[target])


class SwapCards(Action):
    card1: Arg['Card'] = Arg()
    card2: Arg['Card'] = Arg()

    def execute(self, card1: 'Card', card2: 'Card', *, ctx: ActionContext, **kwargs):
        if (not isinstance(card1, Card)) or (not isinstance(card2, Card)):
            return ActionOutcome(success=False)

        if card1.controller_id == card2.controller_id:
            return ActionOutcome(success=False)

        if card1.zone is not card2.zone:
            return ActionOutcome(success=False)

        zone = card1.zone
        if zone not in (CardZone.HAND, CardZone.DECK):
            return ActionOutcome(success=False)

        # Store IDs of original controllers beforehand, as swapping cards causes them to change
        card1_controller_id = card1.controller_id
        card2_controller_id = card2.controller_id

        ctx.game.remove_card_from_current_zone(card1)
        ctx.game.remove_card_from_current_zone(card2)
        ctx.game.add_card_to_zone(card1, card2_controller_id, zone)
        ctx.game.add_card_to_zone(card2, card1_controller_id, zone)
        ctx.game.rules.invalidate()

        return ActionOutcome(
            success=True,
            affected=[card1, card2],
        )


def _create_play_results(
    source_id: PlayerId | int,
    card: Card,
    player: Player,
    target: Entity | None,
    is_played: bool,
    has_need_condition: bool,
    need_fulfilled: bool,
) -> tuple[ActionResult, ...]:
    card_snapshot = card.to_snapshot()
    target_snapshot = (
        target.to_snapshot()
        if target is not None
        else None
    )

    results: list[ActionResult] = []

    if is_played:
        results.append(
            CardPlayedResult(
                source_id=source_id,
                player_id=player.id,
                card_id=card.id,
                card=card_snapshot,
                has_need_condition=has_need_condition,
                need_fulfilled=need_fulfilled,
            )
        )

    if isinstance(card, Monster):
        results.append(
            MonsterSummonedResult(
                source_id=source_id,
                player_id=player.id,
                monster_id=card.id,
                monster=card_snapshot,
                target=target_snapshot,
                is_played=is_played,
            )
        )

    elif isinstance(card, Spell):
        results.append(
            SpellCastResult(
                source_id=source_id,
                player_id=player.id,
                card_id=card.id,
                card=card_snapshot,
                target=target_snapshot,
                is_played=is_played,
            )
        )

    return tuple(results)


class Summon(Action):
    card: Arg['Monster'] = Arg(many=True)
    controller: Arg['Player'] = Arg()
    pos: Arg[int | None] = Arg(default=None)
    attack: Arg[int | None] = Arg(default=None)
    hp: Arg[int | None] = Arg(default=None)
    is_played: Arg[bool] = Arg(default=False)
    has_need_condition: Arg[bool] = Arg(default=False)
    need_fulfilled: Arg[bool] = Arg(default=False)
    emit_results: Arg[bool] = Arg(default=True)

    def execute(
        self,
        card: 'Monster',
        controller: 'Player',
        pos: int | None,
        attack: int | None,
        hp: int | None,
        is_played: bool,
        has_need_condition: bool,
        need_fulfilled: bool,
        emit_results: bool,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(card, Monster):
            return ActionOutcome(success=False)

        if card.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        if len(controller.board) == controller.board.MAX_CARDS:
            return ActionOutcome(success=False)

        ok, pos, reason = ctx.game.resolve_summon_position(controller, pos)
        if not ok:
            return ActionOutcome(success=False)

        if (attack is not None) or (hp is not None):
            card.set_base_stats(attack=attack, hp=hp)

        ctx.game.move_card(card, controller.id, CardZone.BOARD, pos=pos)

        play_results = _create_play_results(
            source_id=ctx.source.id,
            card=card,
            player=controller,
            target=ctx.env.get('magic_effect_target'),
            is_played=is_played,
            has_need_condition=has_need_condition,
            need_fulfilled=need_fulfilled,
        )

        return ActionOutcome(
            success=True,
            results=play_results if emit_results else (),
            presentation_results= None if emit_results else play_results,
            affected=[card],
        )


class Play(Action):
    player: Arg['Player'] = Arg()
    card: Arg['Card'] = Arg()
    pos: Arg[int | None] = Arg(default=None)
    target: Arg[Entity | None] = Arg(default=None)

    # for manual play UX (allow canceling target selection)
    allow_cancel: Arg[bool] = Arg(default=False)

    def execute(self, player: 'Player', card: 'Card', pos: int | None, target: Entity | None, allow_cancel: bool, *, ctx: ActionContext, **kwargs):
        if not isinstance(card, Card):
            return ActionOutcome(success=False)

        if card.controller_id != player.id or card.zone is not CardZone.HAND:
            return ActionOutcome(success=False)

        cost = card.cost
        if player.gold < cost:
            return ActionOutcome(success=False)

        if isinstance(card, Monster):
            ok, pos, reason = ctx.game.resolve_summon_position(player, pos)
            if not ok:
                return ActionOutcome(success=False)

        skip_magic = False

        if card.targets is not None:
            options = ctx.game.play_target_options(card=card, player=player, pos=pos)

            if target is None:
                if len(options) == 0:
                    if isinstance(card, Spell):
                        # Spell is not playable without targets
                        return ActionOutcome(success=False)

                    # Monster is playable without targets, but its Magic gets skipped
                    skip_magic = True

                else:
                    prompt = ChooseEntityPrompt(
                        options=options,
                    )
                    id_to_obj = {int(o.id): o for o in options}

                    def _on_choose(response: ChoiceResponse):
                        if not response.selected_option_ids:
                            # Cancel => do nothing
                            return []

                        chosen_id = response.selected_option_ids[0]
                        chosen = id_to_obj[chosen_id]

                        # Continue by re-enqueuing Play() with a chosen target
                        return [Play(player=player, card=card, pos=pos, target=chosen)]

                    return ActionOutcome(
                        success=True,
                        pending_request=PendingChoiceRequest(
                            request_id=ctx.game.alloc_request_id(),
                            player_id=player.id,
                            prompt=prompt,
                            on_choose=_on_choose,
                            allow_cancel=allow_cancel,
                        )
                    )

            else:
                # If target is provided, validate it is legal
                if target not in options:
                    return ActionOutcome(success=False)

        # Need is a play-time condition. It must be evaluated while the card
        # is still in hand and then remain fixed for this play.
        has_need_condition = card.has_need_condition()
        need_fulfilled = (
            ctx.game.card_need_fulfilled(card)
            if has_need_condition
            else False
        )

        spend_gold_calls = [
            ActionCall(
                SpendGold(
                    player=player,
                    amount=cost,
                    reason='play_spell' if isinstance(card, Spell) else 'play_monster',
                    card=card.to_snapshot(),
                    is_generated=card.is_generated,
                ),
                source=card,
            ),
        ]

        # Move the played card out of hand temporarily.
        # This lets a Loop copy enter the hand even if the hand
        # had 7 cards before the play, because the played card freed one slot.
        ctx.game.move_card(card, player.id, CardZone.INVALID)

        loop_calls = []
        loop_copy = None
        loop_counters = card.get_status(CardStatusId.LOOP)

        if loop_counters >= 1:
            loop_copy = ctx.game.create_card_copy(
                card,
                controller_id=card.controller_id,
                creator_id=card.id,
                creator_base_identity=card.base_identity,
            )
            loop_copy.set_status(CardStatusId.LOOP, loop_counters - 1)
            loop_calls.append(ActionCall(Move(target=loop_copy, zone=CardZone.HAND), source=card))

        if isinstance(card, Monster):
            # Synergy: The monster will trigger its effect when played
            # and if an ally monster of the same tribe has been played this turn.
            def tribes_overlap(a: set[Tribe] | tuple[Tribe, ...], b: set[Tribe] | tuple[Tribe, ...]) -> bool:
                if (not a) or (not b):
                    return False

                if (Tribe.ALL in a) or (Tribe.ALL in b):
                    return True

                return not set(a).isdisjoint(b)

            synergy_triggered = False
            if len(card.tribes) > 0 and tribes_overlap(card.tribes, player.tribes_played_this_turn):
                synergy_triggered = True

            magic_calls = []
            synergy_calls = []

            if not skip_magic:
                # Magic: The card will trigger its effect when played.
                if (not has_need_condition) or need_fulfilled:
                    effect = card.get_ability(Ability.MAGIC)
                    if effect is not None:
                        magic_calls.append(
                            ActionCall(
                                TriggerAbility(target=card, ability=Ability.MAGIC),
                                source=card,
                                env={'target': target, 'loop_copy': loop_copy, 'synergy_triggered': synergy_triggered},
                            )
                        )

                if synergy_triggered:
                    synergy_effect = card.get_ability(Ability.SYNERGY)
                    if synergy_effect is not None:
                        synergy_calls.append(
                            ActionCall(
                                TriggerAbility(target=card, ability=Ability.SYNERGY),
                                source=card,
                                env={'target': target, 'loop_copy': loop_copy},
                            )
                        )

            player.tribes_played_this_turn.update(card.tribes)

            return ActionOutcome(
                success=True,
                affected=[card],
                action_calls=[
                    *spend_gold_calls,
                    *loop_calls,
                    ActionCall(
                        Summon(
                            card=card,
                            controller=player,
                            pos=pos,
                            is_played=True,
                            has_need_condition=has_need_condition,
                            need_fulfilled=need_fulfilled,
                            emit_results=False,
                        ),
                        source=player,
                        env={'magic_effect_target': target},  # used only for result logging
                    ),
                    *magic_calls,
                    *synergy_calls,
                    ActionCall(
                        EmitPlayResults(
                            card=card,
                            player=player,
                            target=target,
                            is_played=True,
                            has_need_condition=has_need_condition,
                            need_fulfilled=need_fulfilled,
                        ),
                        source=player,
                    ),
                ],
            )

        if isinstance(card, Spell):
            # Shock: After you cast a spell with a base cost of 2 or more, trigger this effect.
            # (note: Shock triggers only when a spell is played by a player and not if it's cast by another effect)
            shock_calls = []
            if card.base.cost >= 2:
                for effect, source in ctx.game.collect_ability_listener_effects(Ability.SHOCK, player=player):
                    shock_calls.append(
                        ActionCall(
                            TriggerAbility(target=source, ability=Ability.SHOCK),
                            source=source,
                            env={'trigger_card': card, 'target': target},
                        )
                    )

            return ActionOutcome(
                success=True,
                affected=[card],
                action_calls=[
                    *spend_gold_calls,
                    *loop_calls,
                    ActionCall(
                        Cast(
                            card=card,
                            controller=player,
                            effect_target=target,
                            is_played=True,
                            has_need_condition=has_need_condition,
                            need_fulfilled=need_fulfilled,
                        ),
                        source=player,
                        env={'loop_copy': loop_copy},
                    ),
                    *shock_calls,
                ],
            )


class Cast(Action):
    card: Arg['Spell'] = Arg(many=True)
    controller: Arg['Player'] = Arg()
    effect_target: Arg[Entity | Literal['random'] | None] = Arg(default=None)
    is_played: Arg[bool] = Arg(default=False)
    has_need_condition: Arg[bool] = Arg(default=False)
    need_fulfilled: Arg[bool] = Arg(default=False)

    def execute(
        self,
        card: Spell,
        controller: 'Player',
        effect_target: Entity | Literal['random'] | None,
        is_played: bool,
        has_need_condition: bool,
        need_fulfilled: bool,
        *,
        ctx: ActionContext,
        **kwargs
    ):
        if not isinstance(card, Card):
            return ActionOutcome(success=False)

        if card.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        # If a spell is cast by an effect, any choices caused by this `Cast` should be made randomly.
        if not is_played:
            ctx.env['_auto_choose'] = True

        should_pick_random_target = (
            effect_target == 'random'
            or (
                (not is_played)
                and (card.targets is not None)
                and (effect_target is None)
            )
        )

        if should_pick_random_target:
            options = ctx.game.play_target_options(card=card, player=controller)
            if len(options) == 0:
                effect_target = None
            else:
                effect_target = ctx.game.rng.choice(options)

        ctx.game.move_card(card, controller.id, CardZone.STACK)

        play_presentation_results = _create_play_results(
            source_id=ctx.source.id,
            card=card,
            player=controller,
            target=effect_target,
            is_played=is_played,
            has_need_condition=has_need_condition,
            need_fulfilled=need_fulfilled,
        )

        magic_calls = []
        need_blocks_magic = (
            is_played
            and has_need_condition
            and not need_fulfilled
        )
        skip_magic = need_blocks_magic or ((card.targets is not None) and (effect_target is None))
        if not skip_magic:
            effect = card.get_ability(Ability.MAGIC)
            if effect is not None:
                magic_calls.append(
                    ActionCall(
                        TriggerAbility(target=card, ability=Ability.MAGIC),
                        source=card,
                        env={'target': effect_target, 'loop_copy': ctx.env.get('loop_copy', None)},
                    )
                )

        return ActionOutcome(
            success=True,
            affected=[card],
            presentation_results=play_presentation_results,
            action_calls=[
                *magic_calls,
                ActionCall(RemoveCardFromStack(card=card), source=card),
                ActionCall(
                    EmitPlayResults(
                        card=card,
                        player=controller,
                        target=effect_target,
                        is_played=is_played,
                        has_need_condition=has_need_condition,
                        need_fulfilled=need_fulfilled,
                    ),
                    source=ctx.source,
                ),
            ],
        )


class RemoveCardFromStack(Action):
    card: Arg['Card'] = Arg()

    def execute(self, card: 'Card', *, ctx: ActionContext, **kwargs):
        assert card.zone is CardZone.STACK, f"Card is not on stack: {card.zone}"
        ctx.game.move_card(card, card.controller_id, CardZone.INVALID)
        return ActionOutcome(success=True, affected=[card])


class EmitPlayResults(Action):
    card: Arg['Card'] = Arg()
    player: Arg['Player'] = Arg()
    target: Arg[Entity | None] = Arg(default=None)
    is_played: Arg[bool] = Arg(default=False)
    has_need_condition: Arg[bool] = Arg(default=False)
    need_fulfilled: Arg[bool] = Arg(default=False)

    def execute(
        self,
        card: Card,
        player: Player,
        target: Entity | None,
        is_played: bool,
        has_need_condition: bool,
        need_fulfilled: bool,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        results = _create_play_results(
            source_id=ctx.source.id,
            card=card,
            player=player,
            target=target,
            is_played=is_played,
            has_need_condition=has_need_condition,
            need_fulfilled=need_fulfilled,
        )

        return ActionOutcome(
            success=True,
            results=results,
            presentation_results=(),
            affected=[card],
        )


class TriggerAbility(Action):
    target: Arg['Entity'] = Arg(many=True)
    ability: Arg[Ability] = Arg()

    def execute(self, target: Entity, ability: Ability, *, ctx: ActionContext, **kwargs):
        effect = target.get_ability(ability)
        if effect is None:
            return ActionOutcome(success=True)

        return ActionOutcome(
            success=True,
            results=(
                AbilityTriggeredResult(
                    source_id=target.id,
                    entity_id=target.id,
                    entity=target.to_snapshot(),
                    ability=ability,
                ),
            ),
            action_calls=[ActionCall(effect, source=target, vars=ctx.vars.copy())],
        )


class ToggleAbility(Action):
    target: Arg['Monster'] = Arg(many=True)
    ability: Arg[Ability] = Arg()
    enabled: Arg[bool] = Arg()

    def execute(self, target: Monster, ability: Ability, enabled: bool, *, ctx: ActionContext, **kwargs):
        if target.zone is not CardZone.BOARD:
            return ActionOutcome(success=False)

        target.toggle_ability(CardToggleableAbility(ability.value), enabled)
        return ActionOutcome(success=True, affected=[target])


class Catch(Action):
    catcher: Arg['Monster'] = Arg()
    card_to_catch: Arg['Card'] = Arg()

    def execute(self, catcher: 'Monster', card_to_catch: 'Card', *, ctx: ActionContext, **kwargs):
        if not isinstance(card_to_catch, Card):
            return ActionOutcome(success=False)

        if catcher.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        if card_to_catch.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        # If catcher already has a caught card, fizzle.
        if catcher.caught_card is not None:
            return ActionOutcome(success=False)

        ctx.game.move_card(card_to_catch, card_to_catch.controller_id, CardZone.INVALID)
        catcher.caught_card = CaughtCardData(
            template_id=card_to_catch.template.id,
            controller_id=card_to_catch.controller_id,
        )

        return ActionOutcome(success=True, affected=[catcher, card_to_catch])


class ReleaseCaughtCard(Action):
    catcher: Arg['Monster'] = Arg()
    var: Arg['Var'] = Arg(raw=True)  # raw=True prevents turning `var` into a value

    def execute(self, catcher: 'Monster', var: 'Var', *, ctx: ActionContext, **kwargs):
        if not isinstance(catcher, Monster):
            return ActionOutcome(success=False)

        if catcher.caught_card is None:
            return ActionOutcome(success=False)

        ctx.vars[var.name] = ctx.game.create_card(
            template_id=catcher.caught_card.template_id,
            controller_id=catcher.caught_card.controller_id,
            creator_id=catcher.id,
            creator_base_identity=catcher.base_identity,
        )
        catcher.caught_card = None
        return ActionOutcome(success=True)


class Erase(Action):
    target: Arg['Card'] = Arg(many=True)

    def execute(self, target: 'Card', *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)

        if target.zone is CardZone.ERASED:
            return ActionOutcome(success=False)

        ctx.game.move_card(target, target.controller_id, CardZone.ERASED)
        return ActionOutcome(success=True, affected=[target])


class TransformCard(Action):
    target: Arg['Card'] = Arg(many=True)
    new_card: Arg['Card'] = Arg()

    def execute(self, target: 'Card', new_card: 'Card', *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Card):
            return ActionOutcome(success=False)
        if not isinstance(new_card, Card):
            return ActionOutcome(success=False)

        if target.zone not in CARD_EDITABLE_ZONES:
            return ActionOutcome(success=False)

        assert new_card.zone is CardZone.INVALID

        controller_id = target.controller_id
        zone = target.zone

        if target.zone is CardZone.BOARD:
            pos = target.pos
        elif target.zone is CardZone.DECK:
            pos = ctx.game.player(controller_id).deck.get_card_index(target)
        else:
            pos = None

        ctx.game.move_card(target, controller_id, CardZone.INVALID)
        ctx.game.move_card(new_card, controller_id, zone, pos=pos)

        return ActionOutcome(success=True, affected=[target, new_card])


class Attack(Action):
    attacker: Arg['Monster'] = Arg()
    defender: Arg['Monster | Player'] = Arg(many=True)

    def execute(self, attacker: 'Monster', defender: 'Monster | Player', *, ctx: ActionContext, **kwargs):
        if not isinstance(attacker, Monster):
            return ActionOutcome(success=False)
        if not isinstance(defender, (Monster, Player)):
            return ActionOutcome(success=False)

        if attacker.zone is not CardZone.BOARD:
            return ActionOutcome(success=False)
        if isinstance(defender, Monster) and defender.zone is not CardZone.BOARD:
            return ActionOutcome(success=False)

        attacker.has_attacked = True
        ctx.env['combat_result'] = {}  # shared between CombatDamage and AttackAftermath

        # Support: This monster will trigger its effect each time another ally monster attacks.
        support_calls = []
        for effect, source in ctx.game.collect_ability_listener_effects(
            Ability.SUPPORT,
            player=ctx.game.player(attacker.controller_id),
            board_only=True,
        ):
            if source is attacker:
                continue

            support_calls.append(
                ActionCall(
                    TriggerAbility(target=source, ability=Ability.SUPPORT),
                    source=source,
                    env={'attacker': attacker, 'defender': defender},
                )
            )

        return ActionOutcome(
            success=True,
            results=(
                AttackDeclaredResult(
                    source_id=ctx.source.id,
                    attacker_id=attacker.id,
                    attacker=attacker.to_snapshot(),
                    defender_id=defender.id,
                    defender=defender.to_snapshot(),
                ),
            ),
            affected=[attacker, defender],
            action_calls=[
                *support_calls,
                ActionCall(CombatDamage(attacker=attacker, defender=defender), source=attacker, env=ctx.env),
                ActionCall(AttackAftermath(attacker=attacker, defender=defender), source=attacker, env=ctx.env),
            ],
        )


class CombatDamage(Action):
    attacker: Arg['Monster'] = Arg()
    defender: Arg['Monster | Player'] = Arg()

    def execute(self, attacker: 'Monster', defender: 'Monster | Player', *, ctx: ActionContext, **kwargs):
        if attacker.zone is not CardZone.BOARD:
            return ActionOutcome(success=False)
        if isinstance(defender, Monster) and defender.zone is not CardZone.BOARD:
            return ActionOutcome(success=False)

        if isinstance(defender, Player):
            res = ctx.game.apply_damage(
                target=defender,
                damage=attacker.attack,
                source=attacker,
                kind=DamageKind.COMBAT,
                combat_attacker=attacker,
                combat_defender=defender,
            )
            ctx.env['combat_result'].update({
                'damage_to_attacker': 0,
                'damage_to_defender': res.damage,
                'attacker_dead': False,
                'defender_dead': res.killed,
                'attacker_snapshot': attacker.to_snapshot(),
                'defender_snapshot': defender.to_snapshot(),
            })

            return ActionOutcome(
                success=True,
                results=res.results,
                affected=[attacker, defender],
                action_calls=res.extra_actions,
            )

        # Snapshot to avoid dynamic stat recalculations
        attacker_attack = attacker.attack
        defender_attack = defender.attack

        attacker_res = ctx.game.apply_damage(
            target=defender,
            damage=attacker_attack,
            source=attacker,
            kind=DamageKind.COMBAT,
            combat_attacker=attacker,
            combat_defender=defender,
        )
        defender_res = ctx.game.apply_damage(
            target=attacker,
            damage=defender_attack,
            source=defender,
            kind=DamageKind.COMBAT,
            combat_attacker=attacker,
            combat_defender=defender,
        )

        ctx.env['combat_result'].update({
            'damage_to_attacker': defender_res.damage,
            'damage_to_defender': attacker_res.damage,
            'attacker_dead': defender_res.killed,
            'defender_dead': attacker_res.killed,
            'attacker_snapshot': attacker.to_snapshot(),
            'defender_snapshot': defender.to_snapshot(),
        })

        return ActionOutcome(
            success=True,
            results=[*attacker_res.results, *defender_res.results],
            affected=[attacker, defender],
            # If both monsters die from simultaneous combat damage, the attacker's
            # Kill/Dust chain must resolve before the defender's.
            action_calls=[*defender_res.extra_actions, *attacker_res.extra_actions],
        )


class AttackAftermath(Action):
    attacker: Arg['Monster'] = Arg()
    defender: Arg['Monster | Player'] = Arg()

    def execute(self, attacker: 'Monster', defender: 'Monster | Player', *, ctx: ActionContext, **kwargs):
        if not ctx.env['combat_result']:
            # CombatDamage action failed
            return ActionOutcome(success=False)

        if attacker.zone is CardZone.BOARD:
            attacker.remove_keyword(CardKeyword.CHARGE)
            attacker.remove_keyword(CardKeyword.HASTE)

        return ActionOutcome(
            success=True,
            results=(
                AttackResolvedResult(
                    source_id=ctx.source.id,
                    attacker_id=attacker.id,
                    attacker=ctx.env['combat_result']['attacker_snapshot'],
                    defender_id=defender.id,
                    defender=ctx.env['combat_result']['defender_snapshot'],
                    damage_to_attacker=ctx.env['combat_result']['damage_to_attacker'],
                    damage_to_defender=ctx.env['combat_result']['damage_to_defender'],
                    attacker_dead=ctx.env['combat_result']['attacker_dead'],
                    defender_dead=ctx.env['combat_result']['defender_dead'],
                ),
            ),
            affected=[attacker, defender],
        )


class RefreshAttacks(Action):
    target: Arg['Monster'] = Arg(many=True)

    def execute(self, target: 'Monster', *, ctx: ActionContext, **kwargs):
        if not isinstance(target, Monster):
            return ActionOutcome(success=False)

        if target.zone is not CardZone.BOARD:
            return ActionOutcome(success=False)

        target.has_attacked = False

        return ActionOutcome(
            success=True,
            affected=[target],
        )


class EarnGold(Action):
    player: Arg['Player'] = Arg(many=True)
    amount: Arg[int] = Arg()

    def execute(self, player: 'Player', amount: int, *, ctx: ActionContext, **kwargs):
        if not isinstance(player, Player):
            return ActionOutcome(success=False)

        if amount <= 0:
            return ActionOutcome(success=False)

        player.gold += amount
        return ActionOutcome(success=True, affected=[player])


class SpendGold(Action):
    player: Arg['Player'] = Arg(many=True)
    amount: Arg[int] = Arg()
    allow_partial: Arg[bool] = Arg(default=False)
    reason: Arg[GoldSpendReason] = Arg(default='effect')
    card: Arg[CardSnapshot | None] = Arg(default=None)
    is_generated: Arg[bool] = Arg(default=False)

    def execute(
        self,
        player: 'Player',
        amount: int,
        allow_partial: bool,
        reason: GoldSpendReason,
        card: CardSnapshot | None,
        is_generated: bool,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        assert amount >= 0

        if player.gold < amount:
            if allow_partial:
                amount = player.gold
                if amount == 0:
                    return ActionOutcome(success=False)

            else:
                return ActionOutcome(success=False)

        if amount == 0:
            return ActionOutcome(success=True)

        player.gold -= amount

        return ActionOutcome(
            success=True,
            results=[
                GoldSpentResult(
                    source_id=ctx.source.id,
                    player_id=player.id,
                    amount=amount,
                    reason=reason,
                    card=card,
                    is_generated=is_generated,
                ),
            ],
            affected=[player],
        )


class SetGold(Action):
    player: Arg['Player'] = Arg(many=True)
    amount: Arg[int] = Arg()

    def execute(self, player: 'Player', amount: int, *, ctx: ActionContext, **kwargs):
        player.gold = amount
        return ActionOutcome(success=True, affected=[player])


class AddArtifact(Action):
    player: Arg['Player'] = Arg(many=True)
    artifact: Arg['type[Artifact]'] = Arg()

    def execute(self, player: 'Player', artifact: 'type[Artifact]', *, ctx: ActionContext, **kwargs):
        if any(existing.name == artifact.name for existing in player.artifacts):
            return ActionOutcome(success=False)

        new_artifact_obj = artifact(id=ctx.game.alloc_entity_id(), controller_id=player.id)
        ctx.game.register_entity(new_artifact_obj, entity_id=new_artifact_obj.id)

        player.artifacts.append(new_artifact_obj)

        return ActionOutcome(success=True, affected=[new_artifact_obj])


class ToggleArtifact(Action):
    artifact: Arg['Artifact'] = Arg()
    enabled: Arg[bool] = Arg()

    def execute(self, artifact: 'Artifact', enabled: bool, *, ctx: ActionContext, **kwargs):
        artifact.toggle(enabled)
        return ActionOutcome(success=True, affected=[artifact])


class TransformArtifact(Action):
    player: Arg['Player'] = Arg()
    artifact: Arg['Artifact'] = Arg()
    new_artifact: Arg['type[Artifact]'] = Arg()

    def execute(self, player: 'Player', artifact: 'Artifact', new_artifact: 'type[Artifact]', *, ctx: ActionContext, **kwargs):
        if artifact not in player.artifacts:
            return ActionOutcome(success=False)

        new_artifact_obj = new_artifact(id=ctx.game.alloc_entity_id(), controller_id=player.id)
        ctx.game.register_entity(new_artifact_obj, entity_id=new_artifact_obj.id)

        index = player.artifacts.index(artifact)
        player.artifacts[index] = new_artifact_obj

        return ActionOutcome(success=True, affected=[artifact, new_artifact_obj])


class UpdateArtifactCounter(Action):
    artifact: Arg['Artifact'] = Arg()
    delta: Arg[int] = Arg()

    def execute(self, artifact: 'Artifact', delta: int, *, ctx: ActionContext, **kwargs):
        artifact.counter = max(artifact.counter + delta, 0)
        return ActionOutcome(success=True, affected=[artifact])


class Enchant(Action):
    slot: Arg['BoardSlot'] = Arg(many=True)
    enchantment: Arg['type[Enchantment]'] = Arg()

    def execute(
        self,
        slot: BoardSlot,
        enchantment: type[Enchantment],
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(slot, BoardSlot):
            return ActionOutcome(success=False)

        results: list[ActionResult] = []

        replaced_enchantment = ctx.game.enchantment_on_slot(slot)
        replaced_snapshot = None

        if replaced_enchantment is not None:
            replaced_snapshot = replaced_enchantment.to_snapshot()
            ctx.game.remove_enchantment(replaced_enchantment)

            results.append(
                EnchantmentRemovedResult(
                    source_id=ctx.source.id,
                    player_id=slot.controller_id,
                    slot_id=slot.id,
                    slot=slot.to_snapshot(),
                    enchantment_id=replaced_enchantment.id,
                    enchantment=replaced_snapshot,
                    reason='replaced',
                )
            )

        new_enchantment = ctx.game.create_enchantment(
            enchantment,
            slot,
            creator_id=ctx.source.id,
            creator_base_identity=ctx.source.base_identity,
        )

        results.append(
            BoardSlotEnchantedResult(
                source_id=ctx.source.id,
                player_id=slot.controller_id,
                slot_id=slot.id,
                slot=slot.to_snapshot(),
                enchantment_id=new_enchantment.id,
                enchantment=new_enchantment.to_snapshot(),
                replaced_enchantment=replaced_snapshot,
            )
        )

        return ActionOutcome(success=True, results=results)


class RemoveEnchantment(Action):
    target: Arg['Enchantment | BoardSlot'] = Arg(many=True)
    reason: Arg[EnchantmentRemovalReason] = Arg(default='removed')

    def execute(
        self,
        target: Enchantment | BoardSlot,
        reason: EnchantmentRemovalReason,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if isinstance(target, BoardSlot):
            enchantment = ctx.game.enchantment_on_slot(target)
            if enchantment is None:
                return ActionOutcome(success=False)

            slot = target

        elif isinstance(target, Enchantment):
            if not target.active:
                return ActionOutcome(success=False)

            slot_entity = ctx.game.entity(target.slot_id)
            if not isinstance(slot_entity, BoardSlot):
                return ActionOutcome(success=False)

            if slot_entity.enchantment_id != target.id:
                return ActionOutcome(success=False)

            enchantment = target
            slot = slot_entity

        else:
            return ActionOutcome(success=False)

        if not ctx.game.remove_enchantment(enchantment):
            return ActionOutcome(success=False)

        return ActionOutcome(
            success=True,
            results=(
                EnchantmentRemovedResult(
                    source_id=ctx.source.id,
                    player_id=slot.controller_id,
                    slot_id=slot.id,
                    slot=slot.to_snapshot(),
                    enchantment_id=enchantment.id,
                    enchantment=enchantment.to_snapshot(),
                    reason=reason,
                ),
            ),
        )


class TransformEnchantment(Action):
    target: Arg['Enchantment'] = Arg(many=True)
    enchantment: Arg['type[Enchantment]'] = Arg()

    def execute(
        self,
        target: Enchantment,
        enchantment: type[Enchantment],
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(target, Enchantment):
            return ActionOutcome(success=False)

        if not target.active:
            return ActionOutcome(success=False)

        slot_entity = ctx.game.entity(target.slot_id)
        if not isinstance(slot_entity, BoardSlot):
            return ActionOutcome(success=False)

        if slot_entity.enchantment_id != target.id:
            return ActionOutcome(success=False)

        old_snapshot = target.to_snapshot()
        old_slot_snapshot = slot_entity.to_snapshot()
        ctx.game.remove_enchantment(target)

        new_enchantment = ctx.game.create_enchantment(
            enchantment,
            slot_entity,
            creator_id=ctx.source.id,
            creator_base_identity=ctx.source.base_identity,
        )

        return ActionOutcome(
            success=True,
            results=(
                EnchantmentRemovedResult(
                    source_id=ctx.source.id,
                    player_id=slot_entity.controller_id,
                    slot_id=slot_entity.id,
                    slot=old_slot_snapshot,
                    enchantment_id=target.id,
                    enchantment=old_snapshot,
                    reason='transformed',
                ),
                BoardSlotEnchantedResult(
                    source_id=ctx.source.id,
                    player_id=slot_entity.controller_id,
                    slot_id=slot_entity.id,
                    slot=slot_entity.to_snapshot(),
                    enchantment_id=new_enchantment.id,
                    enchantment=new_enchantment.to_snapshot(),
                    replaced_enchantment=old_snapshot,
                ),
            ),
        )


class UpdateEnchantmentCounter(Action):
    enchantment: Arg['Enchantment'] = Arg(many=True)
    delta: Arg[int] = Arg()

    def execute(
        self,
        enchantment: Enchantment,
        delta: int,
        *,
        ctx: ActionContext,
        **kwargs,
    ):
        if not isinstance(enchantment, Enchantment):
            return ActionOutcome(success=False)

        if not enchantment.active:
            return ActionOutcome(success=False)

        enchantment.counter = max(enchantment.counter + delta, 0)
        return ActionOutcome(success=True)


class ScheduleEffect(Action):
    target: Arg['Entity'] = Arg(many=True)
    name: Arg[str] = Arg()

    def execute(self, target: 'Entity', name: str, *, ctx: ActionContext, **kwargs):
        ctx.game.schedule_effect(target.id, name, ctx)
        return ActionOutcome(success=True, affected=[target])


def ScheduleDelayEffect(target: 'Entity') -> ScheduleEffect:
    return ScheduleEffect(target=target, name='delay')


class SkipNextTurn(Action):
    player: Arg['Player'] = Arg()

    def execute(self, player: 'Player', *, ctx: ActionContext, **kwargs):
        player.turns_to_skip += 1
        return ActionOutcome(success=True)


class AdvanceTurn(Action):
    player: Arg['Player'] = Arg()

    def execute(self, player: 'Player', *, ctx: ActionContext, **kwargs):
        player.tribes_played_this_turn = set()

        if list(ctx.game.players.values())[-1] == player:
            ctx.game.turn += 1

        ctx.game.turn_player = next(p for p in ctx.game.players.values() if p is not player)

        return ActionOutcome(success=True)


class ResolveScheduledEffectsAction(Action):
    def execute(self, *, ctx: ActionContext, **kwargs):
        action_calls = []
        for effect in ctx.game.scheduled_effects:
            entity = ctx.game.entity(effect.entity_id)
            action_calls.append(
                ActionCall(
                    TriggerAbility(target=entity, ability=Ability(effect.name)),
                    source=entity,
                    env=effect.env,
                    vars=effect.vars,
                )
            )

        ctx.game.scheduled_effects = []

        return ActionOutcome(
            success=True,
            action_calls=action_calls,
        )


class PlayerStartTurnAction(Action):
    player: Arg['Player'] = Arg()

    def execute(self, player: 'Player', *, ctx: ActionContext, **kwargs):
        from deltacards.engine.timing_windows import run_player_start_turn_window

        extra_action_calls = []
        if player.turns_to_skip > 0:
            player.turns_to_skip -= 1
            extra_action_calls.append(
                ActionCall(PlayerEndTurnAction(player=player), source=player)
            )

        return ActionOutcome(
            success=True,
            affected=[player],
            action_calls=[
                ActionCall(
                    run_player_start_turn_window,
                    source=player,
                    kwargs={'player': player},
                ),
                *extra_action_calls,
            ],
        )


class PlayerEndTurnAction(Action):
    player: Arg['Player'] = Arg()

    def execute(self, player: 'Player', *, ctx: ActionContext, **kwargs):
        from deltacards.engine.timing_windows import run_player_end_turn_window

        return ActionOutcome(
            success=True,
            affected=[player],
            action_calls=[
                ActionCall(
                    run_player_end_turn_window,
                    source=player,
                    kwargs={'player': player},
                ),
                ActionCall(
                    PlayerStartTurnAction(player=player.opponent),
                    source=player.opponent,
                    kwargs={'player': player.opponent},
                )
            ],
        )
