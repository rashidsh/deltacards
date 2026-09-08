from typing import Any, TYPE_CHECKING

from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardStatusId,
    CardZone,
    DamageKind,
    KillCause,
)

if TYPE_CHECKING:
    from deltacards.actions.standard import (
        AddArtifact,
        AddKeyword,
        Attack,
        Buff,
        Catch,
        Choose,
        Draw,
        DrawNext,
        EarnGold,
        Enchant,
        Erase,
        HalveStats,
        Heal,
        Hit,
        Kill,
        Move,
        Overdraw,
        Paralyze,
        RefreshAttacks,
        ReleaseCaughtCard,
        RemoveEnchantment,
        RemoveKeyword,
        RemoveNegativeEffects,
        RemoveStatus,
        Reveal,
        ScheduleEffect,
        SetBaseStats,
        SetGold,
        SetPlayerHP,
        SetStats,
        SetStatus,
        Silence,
        SpendGold,
        Summon,
        SwapStats,
        ToggleAbility,
        ToggleArtifact,
        TransformArtifact,
        TransformCard,
        TransformEnchantment,
        TriggerAbility,
        UpdateArtifactCounter,
        UpdateEnchantmentCounter,
)
    from deltacards.dsl.vars import Var
    from deltacards.model.artifacts import Artifact


class ActionMethods:
    """
    Action-factory mixin.

    For DSL objects, such as selectors, the action target is the object itself.

    For runtime `Entity` objects, use `ActionProxy` via `entity.actions`:
        monster.actions.buff(attack=+1)
    """

    @property
    def _action_target(self) -> Any:
        return self

    def choose(self, options: Any) -> 'Choose':
        from deltacards.actions.standard import Choose
        return Choose(player=self._action_target, options=options)

    def reveal(self) -> 'Reveal':
        from deltacards.actions.standard import Reveal
        return Reveal(card=self._action_target)

    def hit(self, damage: Any, *, kind: DamageKind | None = None) -> 'Hit':
        from deltacards.actions.standard import Hit
        return Hit(target=self._action_target, damage=damage, kind=kind)

    def heal(self, amount: Any) -> 'Heal':
        from deltacards.actions.standard import Heal
        return Heal(target=self._action_target, amount=amount)

    def kill(
        self,
        *,
        killer: Any = None,
        skip_check_death_prevented: bool = False,
        cause: KillCause = KillCause.DESTROY_EFFECT,
    ) -> 'Kill':
        from deltacards.actions.standard import Kill
        from deltacards.dsl.selectors import SELF
        return Kill(
            target=self._action_target,
            killer=SELF if killer is None else killer,
            skip_check_death_prevented=skip_check_death_prevented,
            cause=cause,
        )

    def buff(
        self,
        *,
        cost: Any = 0,
        attack: Any = 0,
        hp: Any = 0,
        min_cost: Any = None,
        min_attack: Any = None,
        min_hp: Any = None,
    ) -> 'Buff':
        from deltacards.actions.standard import Buff
        return Buff(
            target=self._action_target,
            cost=cost,
            attack=attack,
            hp=hp,
            min_cost=min_cost,
            min_attack=min_attack,
            min_hp=min_hp,
        )

    def set_hp(self, hp: Any) -> 'SetPlayerHP':
        from deltacards.actions.standard import SetPlayerHP
        return SetPlayerHP(player=self._action_target, hp=hp)

    def set_stats(
        self,
        *,
        cost: Any = None,
        attack: Any = None,
        hp: Any = None,
    ) -> 'SetStats':
        from deltacards.actions.standard import SetStats
        return SetStats(
            target=self._action_target,
            cost=cost,
            attack=attack,
            hp=hp,
        )

    def set_base_stats(
        self,
        *,
        cost: Any = None,
        attack: Any = None,
        hp: Any = None,
    ) -> 'SetBaseStats':
        from deltacards.actions.standard import SetBaseStats
        return SetBaseStats(
            target=self._action_target,
            cost=cost,
            attack=attack,
            hp=hp,
        )

    def swap_stats(self) -> 'SwapStats':
        from deltacards.actions.standard import SwapStats
        return SwapStats(target=self._action_target)

    def halve_stats(self, round_up: bool, halve_cost: bool) -> 'HalveStats':
        from deltacards.actions.standard import HalveStats
        return HalveStats(target=self._action_target, round_up=round_up, halve_cost=halve_cost)

    def add_keyword(self, keyword: CardKeyword) -> 'AddKeyword':
        from deltacards.actions.standard import AddKeyword
        return AddKeyword(target=self._action_target, keyword=keyword)

    def remove_keyword(self, keyword: CardKeyword) -> 'RemoveKeyword':
        from deltacards.actions.standard import RemoveKeyword
        return RemoveKeyword(target=self._action_target, keyword=keyword)

    def set_status(self, status_id: CardStatusId, *, value: Any = 1) -> 'SetStatus':
        from deltacards.actions.standard import SetStatus
        return SetStatus(
            target=self._action_target,
            status_id=status_id,
            value=value,
        )

    def remove_status(self, status_id: CardStatusId) -> 'RemoveStatus':
        from deltacards.actions.standard import RemoveStatus
        return RemoveStatus(target=self._action_target, status_id=status_id)

    def silence(self) -> 'Silence':
        from deltacards.actions.standard import Silence
        return Silence(target=self._action_target)

    def paralyze(self) -> 'Paralyze':
        from deltacards.actions.standard import Paralyze
        return Paralyze(target=self._action_target)

    def remove_negative_effects(self) -> 'RemoveNegativeEffects':
        from deltacards.actions.standard import RemoveNegativeEffects
        return RemoveNegativeEffects(target=self._action_target)

    def draw(self, card: Any, *, reason: str = 'effect') -> 'Draw':
        from deltacards.actions.standard import Draw
        return Draw(player=self._action_target, card=card, reason=reason)

    def draw_next(self, *, reason: str = 'effect', from_pos: str = 'top') -> 'DrawNext':
        from deltacards.actions.standard import DrawNext
        return DrawNext(player=self._action_target, reason=reason, from_pos=from_pos)

    def overdraw(self, card: Any) -> 'Overdraw':
        from deltacards.actions.standard import Overdraw
        return Overdraw(player=self._action_target, card=card)

    def move_to(
        self,
        zone: CardZone,
        *,
        controller: Any = None,
        pos: 'int | str | None' = None,
    ) -> 'Move':
        from deltacards.actions.standard import Move
        return Move(
            target=self._action_target,
            zone=zone,
            controller=controller,
            pos=pos,
        )

    def to_hand(self, controller: Any = None, pos: Any = None):
        return self.move_to(CardZone.HAND, controller=controller, pos=pos)

    def to_deck(self, controller: Any = None, pos: Any = None):
        return self.move_to(CardZone.DECK, controller=controller, pos=pos)

    def summon(
        self,
        *,
        controller: Any = None,
        pos: Any = None,
        attack: Any = None,
        hp: Any = None,
    ) -> 'Summon':
        from deltacards.actions.standard import Summon
        from deltacards.dsl.selectors import YOU
        return Summon(
            card=self._action_target,
            controller=YOU if controller is None else controller,
            pos=pos,
            attack=attack,
            hp=hp,
        )

    def erase(self) -> 'Erase':
        from deltacards.actions.standard import Erase
        return Erase(target=self._action_target)

    def turn_into(self, new_card: Any) -> 'TransformCard':
        from deltacards.actions.standard import TransformCard
        return TransformCard(target=self._action_target, new_card=new_card)

    def trigger_ability(self, ability: Ability) -> 'TriggerAbility':
        from deltacards.actions.standard import TriggerAbility
        return TriggerAbility(target=self._action_target, ability=ability)

    def toggle_ability(self, ability: Ability, enabled: bool) -> 'ToggleAbility':
        from deltacards.actions.standard import ToggleAbility
        return ToggleAbility(
            target=self._action_target,
            ability=ability,
            enabled=enabled,
        )

    def catch(self, card_to_catch: Any) -> 'Catch':
        from deltacards.actions.standard import Catch
        return Catch(catcher=self._action_target, card_to_catch=card_to_catch)

    def release_caught_card(self, var: 'Var') -> 'ReleaseCaughtCard':
        from deltacards.actions.standard import ReleaseCaughtCard
        return ReleaseCaughtCard(catcher=self._action_target, var=var)

    def force_attack(self, defender: Any) -> 'Attack':
        from deltacards.actions.standard import Attack
        return Attack(attacker=self._action_target, defender=defender)

    def refresh_attacks(self) -> 'RefreshAttacks':
        from deltacards.actions.standard import RefreshAttacks
        return RefreshAttacks(target=self._action_target)

    def earn_gold(self, amount: Any) -> 'EarnGold':
        from deltacards.actions.standard import EarnGold
        return EarnGold(player=self._action_target, amount=amount)

    def spend_gold(
        self,
        amount: Any,
        *,
        allow_partial: bool = False,
    ) -> 'SpendGold':
        from deltacards.actions.standard import SpendGold
        return SpendGold(
            player=self._action_target,
            amount=amount,
            allow_partial=allow_partial,
        )

    def set_gold(self, amount: Any) -> 'SetGold':
        from deltacards.actions.standard import SetGold
        return SetGold(player=self._action_target, amount=amount)

    def add_artifact(self, artifact: 'Artifact') -> 'AddArtifact':
        from deltacards.actions.standard import AddArtifact
        return AddArtifact(player=self._action_target, artifact=artifact)

    def toggle_artifact(self, enabled: bool) -> 'ToggleArtifact':
        from deltacards.actions.standard import ToggleArtifact
        return ToggleArtifact(artifact=self._action_target, enabled=enabled)

    def transform_artifact(self, new_artifact: 'Artifact') -> 'TransformArtifact':
        from deltacards.actions.standard import TransformArtifact
        from deltacards.dsl.selectors import YOU
        return TransformArtifact(player=YOU, artifact=self._action_target, new_artifact=new_artifact)

    def update_artifact_counter(self, delta: Any) -> 'UpdateArtifactCounter':
        from deltacards.actions.standard import UpdateArtifactCounter
        return UpdateArtifactCounter(artifact=self._action_target, delta=delta)

    def enchant(self, enchantment: Any) -> 'Enchant':
        from deltacards.actions.standard import Enchant
        return Enchant(
            slot=self._action_target,
            enchantment=enchantment,
        )

    def remove_enchantment(
        self,
        *,
        reason: str = 'removed',
    ) -> 'RemoveEnchantment':
        from deltacards.actions.standard import RemoveEnchantment
        return RemoveEnchantment(
            target=self._action_target,
            reason=reason,
        )

    def expire_enchantment(self) -> 'RemoveEnchantment':
        from deltacards.actions.standard import RemoveEnchantment
        return RemoveEnchantment(
            target=self._action_target,
            reason='expired',
        )

    def transform_enchantment(
        self,
        enchantment: Any,
    ) -> 'TransformEnchantment':
        from deltacards.actions.standard import TransformEnchantment
        return TransformEnchantment(
            target=self._action_target,
            enchantment=enchantment,
        )

    def update_enchantment_counter(
        self,
        delta: Any,
    ) -> 'UpdateEnchantmentCounter':
        from deltacards.actions.standard import UpdateEnchantmentCounter
        return UpdateEnchantmentCounter(
            enchantment=self._action_target,
            delta=delta,
        )

    def schedule_delay_effect(self) -> 'ScheduleEffect':
        from deltacards.actions.standard import ScheduleDelayEffect
        return ScheduleDelayEffect(target=self._action_target)


class ActionProxy(ActionMethods):
    """
    Exposes `ActionMethods` for a wrapped runtime object.

    Example:
        monster.actions.buff(attack=+1)
    """

    __slots__ = '_target',

    def __init__(self, target: Any):
        self._target = target

    @property
    def _action_target(self) -> Any:
        return self._target
