import random
import types
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Sequence, TypeVar

from deltacards.actions.base import (
    Action,
    ActionCall,
    ActionContext,
    ActionOutcome,
    evaluate_expr,
)
from deltacards.actions.results import (
    ActionResult,
    AttackResolvedResult,
    CardPlayedResult,
    DodgeConsumedResult,
    EntityDamagedResult,
    MonsterSummonedResult,
)
from deltacards.actions.standard import (
    Kill,
    ReleaseMonsterDeathFinalization,
    TriggerAbility,
)
from deltacards.dsl.core import NoTargetsError, TargetSelector
from deltacards.dsl.vars import Var
from deltacards.engine.action_log import ActionLogRecord
from deltacards.engine.effects import EffectBase, EffectResult, EffectStep, StepResult
from deltacards.engine.modifiers import DamageQuery, RulesEngine
from deltacards.model.cards import Card, CardZone, Monster, Spell, create_card
from deltacards.model.enchantments import Enchantment
from deltacards.model.entity import Entity
from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardStatusId,
    DamageKind,
    KillCause,
    PlayerId,
)
from deltacards.model.player import Player
from deltacards.model.requests import PendingRequest
from deltacards.model.snapshots import CardSnapshot
from deltacards.model.slots import BoardSlot
from deltacards.model.types import BaseIdentity

T = TypeVar('T')


@dataclass(slots=True)
class GameRNG:
    seed: int
    _rng: random.Random = field(repr=False)

    @classmethod
    def from_seed(cls, seed: int) -> 'GameRNG':
        return cls(seed=seed, _rng=random.Random(seed))

    def getstate(self):
        return self._rng.getstate()

    def setstate(self, state) -> None:
        self._rng.setstate(state)

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def choice(self, x: Sequence[T]) -> T:
        return self._rng.choice(x)

    def shuffle(self, x: list[Any]) -> None:
        self._rng.shuffle(x)


@dataclass(slots=True)
class PendingAction:
    action: Any
    source: Entity
    kwargs: dict[str, Any]  # will be passed as kwargs to `action`
    env: dict[str, Any] = field(default_factory=dict)  # used for `TARGET`, `KILLER` etc.
    ctx: ActionContext | None = None  # stores variables and pause/resume context

    send_value: Any | None = None
    step_group_id: int | None = None

    log_group_id: int | None = None
    log_parent_id: int | None = None
    log_depth: int = 0


@dataclass(slots=True)
class StepGroup:
    waiting_coroutine: PendingAction
    remaining: int
    successes: list[bool] = field(default_factory=list)
    results: list[ActionResult] = field(default_factory=list)


@dataclass(slots=True)
class ScheduledEffect:
    entity_id: int
    name: str
    env: dict[str, Any]
    vars: dict[str, Any]


@dataclass(slots=True)
class DamageApplyResult:
    damage: int = 0
    excess_damage: int = 0
    killed: bool = False
    prevented_by: str | None = None
    results: list[ActionResult] = field(default_factory=list)
    extra_actions: list[ActionCall] = field(default_factory=list)


class Game:
    def __init__(self, players: tuple[Player, Player], *, seed: int | None = None):
        if len(players) != 2:
            raise ValueError("Game requires exactly 2 players")

        self.players: dict[PlayerId, Player] = {player.id: player for player in players}
        for player in players:
            player.game = self
            player.opponent = next(other for other in players if other.id != player.id)

        # Random
        if seed is None:
            seed = random.SystemRandom().randint(1, 2**31 - 1)

        self.seed = seed
        self.rng = GameRNG.from_seed(seed)

        # Entities
        self.entities: dict[int, Entity] = {}
        self.next_entity_id = 3  # first two IDs are reserved for players
        self.next_request_id = 1

        # Step groups
        self._next_step_group_id = 1
        self._step_groups: dict[int, StepGroup] = {}

        # Setup state
        self.setup_complete: bool = False
        self.mulligan_offered: dict[PlayerId, list[int]] = {}
        self.mulligan_replacements: dict[PlayerId, set[int]] = {PlayerId.P1: set(), PlayerId.P2: set()}
        self.mulligan_submitted: set[PlayerId] = set()

        # Game over state
        self.game_over = False
        self.dead_players: set[PlayerId] = set()

        self.turn = 1
        self.turn_player: Player = None
        self.action_log: list[ActionLogRecord] = []
        self.log: list[ActionResult] = []
        self.log_by_type: dict[type[ActionResult], list[ActionResult]] = defaultdict(list)
        self.scheduled_effects: list[ScheduledEffect] = []
        self.stack: list[Card] = []
        self.resolution_stack: list[PendingAction] = []
        self.pending_requests: dict[int, 'PendingRequest'] = {}
        self.rules = RulesEngine(self)

        self._next_action_log_id = 1
        self._next_action_log_group_id = 1
        self._next_action_result_id = 1

    def player(self, player_id: PlayerId) -> Player:
        return self.players[player_id]

    def card(self, target_id: int) -> Card:
        entity = self.entities[target_id]
        if not isinstance(entity, Card):
            raise TypeError(f"Entity with ID {target_id} is not a card: {repr(entity)}")

        return entity

    def entity(self, target_id: PlayerId | int) -> Entity:
        if target_id in self.players:
            return self.players[target_id]

        return self.entities[target_id]

    def board_slot(
        self,
        player: Player | PlayerId,
        pos: int,
    ) -> BoardSlot:
        if isinstance(player, PlayerId):
            player = self.player(player)

        if not isinstance(player, Player):
            raise TypeError(
                f"Expected Player or PlayerId, got {type(player).__name__}"
            )

        if not 0 <= pos < player.board.MAX_CARDS:
            raise IndexError(f"Invalid board slot: {pos}")

        return player.board_slots[pos]

    def winner_id(self) -> PlayerId | None:
        if not self.dead_players:
            return None

        if len(self.dead_players) == 2:
            return None

        dead_player_id = list(self.dead_players)[0]
        return dead_player_id.opponent()

    def alloc_entity_id(self) -> int:
        entity_id = self.next_entity_id
        self.next_entity_id += 1
        return entity_id

    def alloc_request_id(self) -> int:
        rid = self.next_request_id
        self.next_request_id += 1
        return rid

    def alloc_action_log_id(self) -> int:
        value = self._next_action_log_id
        self._next_action_log_id += 1
        return value

    def alloc_action_log_group_id(self) -> int:
        value = self._next_action_log_group_id
        self._next_action_log_group_id += 1
        return value

    def register_entity(self, entity: Entity, entity_id: int):
        self.entities[entity_id] = entity

    # --------------------
    # Card utilities
    # --------------------

    def create_card(
        self,
        template_id: int,
        controller_id: PlayerId,
        zone: CardZone = CardZone.INVALID,
        creator_id: int | None = None,
        creator_base_identity: BaseIdentity | None = None,
        base_attack: int | None = None,
        base_hp: int | None = None,
    ) -> Card:
        card_id = self.alloc_entity_id()
        card = create_card(
            id=card_id,
            template_id=template_id,
            controller_id=controller_id,
            zone=zone,
            creator_id=creator_id,
            creator_base_identity=creator_base_identity,
            base_attack=base_attack,
            base_hp=base_hp,
        )
        card.game = self
        self.register_entity(card, entity_id=card_id)
        return card

    def create_card_copy(
        self,
        card: Card | CardSnapshot,
        controller_id: PlayerId,
        creator_id: int | None = None,
        creator_base_identity: BaseIdentity | None = None,
    ) -> Card:
        """Create a base copy from a runtime Card or CardSnapshot."""
        if not isinstance(card, (Card, CardSnapshot)):
            raise TypeError(f"Expected Card or CardSnapshot, got {type(card).__name__}")

        return self.create_card(
            template_id=card.template.id,
            controller_id=controller_id,
            creator_id=creator_id,
            creator_base_identity=creator_base_identity,
        )

    def create_card_copy_exact(
        self,
        card: Card,
        controller_id: PlayerId,
        creator_id: int | None = None,
        creator_base_identity: BaseIdentity | None = None,
    ) -> Card:
        """Create an exact copy of a card."""
        new_card = self.create_card_copy(
            card,
            creator_id=creator_id,
            creator_base_identity=creator_base_identity,
            controller_id=controller_id,
        )
        new_card.copy_exact_state_from(card)
        return new_card

    def remove_card_from_current_zone(self, card: Card) -> None:
        if card.zone is CardZone.STACK:
            self.stack.remove(card)
            return

        controller = self.players[card.controller_id]

        if card.zone is CardZone.BOARD:
            if not isinstance(card, Monster):
                raise TypeError("Only monsters can be in BOARD zone")
            if card.pos is None:
                raise RuntimeError("Card is in BOARD zone, but `pos` is None")
            if controller.board[card.pos] is not card:
                raise RuntimeError("Board position mismatch")

            slot = self.board_slot(controller, card.pos)
            if slot.monster_id != card.id:
                raise RuntimeError(
                    f"Board slot monster mismatch: slot={slot.id}, "
                    f"expected={card.id}, actual={slot.monster_id}"
                )

            slot.monster_id = None
            controller.board[card.pos] = None
            card.pos = None
            card.marked_for_destruction = False

        elif card.zone is CardZone.HAND:
            controller.hand.remove(card.id)
        elif card.zone is CardZone.DECK:
            controller.deck.remove(card.id)
        elif card.zone is CardZone.DUSTPILE:
            controller.dustpile.remove(card.id)
        elif card.zone is CardZone.ERASED:
            controller.erased.remove(card.id)
        elif card.zone is CardZone.INVALID:
            pass
        else:
            raise RuntimeError(f"Invalid zone: {card.zone}")

    def add_card_to_zone(self, card: Card, controller_id: PlayerId, zone: CardZone, pos: int | str | None = None):
        card.controller_id = controller_id
        card.zone = zone

        if card.zone is CardZone.STACK:
            self.stack.append(card)
            return

        controller = self.players[card.controller_id]

        if card.zone is CardZone.BOARD:
            if not isinstance(card, Monster):
                raise TypeError("Only monsters can be in BOARD zone")
            if pos is None or not (0 <= pos < controller.board.MAX_CARDS):
                raise RuntimeError(f"Invalid board position: {pos}")
            if controller.board[pos] is not None:
                raise RuntimeError("Board position is already occupied")

            slot = self.board_slot(controller, pos)
            if slot.monster_id is not None:
                raise RuntimeError(f"Board slot {slot.id} already has monster_id={slot.monster_id}")

            card.pos = pos
            controller.board[card.pos] = card
            slot.monster_id = card.id

        elif card.zone is CardZone.DECK:
            if pos is None:
                pos = self.rng.randint(0, len(controller.deck))
            elif pos == 'top':
                controller.deck.add(card, pos=0)
            elif pos == 'bottom':
                controller.deck.add(card, pos=len(controller.deck))
            elif not isinstance(pos, int):
                raise RuntimeError(f"Invalid deck position: {pos}")

            if isinstance(pos, int):
                controller.deck.add(card, pos=pos)

        elif card.zone is CardZone.HAND:
            if len(controller.hand) >= 7:
                raise RuntimeError("Hand is full")

            controller.hand.add(card)

        elif card.zone is CardZone.DUSTPILE:
            controller.dustpile.add(card)
        elif card.zone is CardZone.ERASED:
            controller.erased.add(card)
        elif card.zone is CardZone.INVALID:
            pass
        else:
            raise RuntimeError(f"Invalid zone: {card.zone}")

    def move_card(
        self,
        card: Card,
        controller_id: PlayerId,
        zone: CardZone,
        pos: int | str | None = None,
    ):
        # Cards aren't allowed to be moved from ERASED zone
        if card.zone is CardZone.ERASED:
            if zone is CardZone.ERASED and controller_id == card.controller_id:
                return

            raise RuntimeError(f"Illegal move from ERASED: {card!r}")

        # Dustpile monsters can only be erased
        if card.zone is CardZone.DUSTPILE:
            if zone is not CardZone.ERASED:
                raise RuntimeError(f"Illegal move from DUSTPILE: {card!r}")

            if controller_id != card.controller_id:
                raise RuntimeError(
                    f"Illegal control change while moving from DUSTPILE: {card!r}, "
                    f"old_controller={card.controller_id}, new_controller={controller_id}"
                )

        if zone is CardZone.DUSTPILE and not isinstance(card, Monster):
            raise RuntimeError(f"Only monsters can be moved to DUSTPILE: {card!r}")

        self.remove_card_from_current_zone(card)
        self.add_card_to_zone(card, controller_id, zone, pos=pos)
        self.rules.invalidate()

    def hold_monster_death_finalization(self, monster: Monster) -> None:
        monster.death_finalization_locks += 1

    def release_monster_death_finalization(self, monster: Monster) -> bool:
        if monster.death_finalization_locks <= 0:
            raise RuntimeError(f"`Game.release_monster_death_finalization()` called without a hold: {monster!r}")

        monster.death_finalization_locks -= 1

        if monster.death_finalization_locks == 0 and monster.death_pending:
            return self.finalize_monster_death(monster)

        return False

    def move_monster_to_pending_death_state(self, monster: Monster) -> None:
        """
        Remove a killed monster from board without resetting runtime state.

        The monster becomes temporary placed in `CardZone.INVALID`.
        Abilities such as Dust can still use `SELF` to read its stats, buffs, caught-card data, etc.
        """
        if monster.zone is not CardZone.BOARD:
            raise RuntimeError(f"Invalid move to pending death: {monster!r}")

        if monster.pos is None:
            raise RuntimeError(f"Invalid board position: {monster.pos}")

        if monster.death_finalization_locks <= 0:
            raise RuntimeError(f"Monster has no death finalization locks: {monster!r}")

        controller = self.players[monster.controller_id]

        if controller.board[monster.pos] is not monster:
            raise RuntimeError("Board position mismatch")

        slot = self.board_slot(controller, monster.pos)
        if slot.monster_id != monster.id:
            raise RuntimeError(f"Board slot monster mismatch for dying monster {monster.id}")

        slot.monster_id = None
        controller.board[monster.pos] = None
        monster.pos = None

        monster._zone = CardZone.INVALID

        monster.marked_for_destruction = True
        monster.death_pending = True

        self.rules.invalidate()

    def finalize_monster_death(self, monster: Monster) -> bool:
        """Finish death processing for a monster."""
        if not monster.death_pending:
            return False

        if monster.death_finalization_locks > 0:
            return False

        monster.marked_for_destruction = False
        monster.death_pending = False

        # If it's still in `CardZone.INVALID`, reset it and move it to dustpile
        if monster.zone is CardZone.INVALID:
            monster._reset()
            self.move_card(monster, monster.controller_id, CardZone.DUSTPILE)
            return True

        if monster.zone is CardZone.ERASED:
            monster._reset()
            self.rules.invalidate()
            return True

        # If a monster was moved somewhere else by an effect, do not reset it
        self.rules.invalidate()
        return False

    # --------------------
    # Enchantments
    # --------------------

    def enchantment_on_slot(
        self,
        slot: BoardSlot,
    ) -> Enchantment | None:
        if not isinstance(slot, BoardSlot):
            raise TypeError(
                f"Expected BoardSlot, got {type(slot).__name__}"
            )

        if slot.enchantment_id is None:
            return None

        entity = self.entity(slot.enchantment_id)
        if not isinstance(entity, Enchantment):
            raise RuntimeError(
                f"Slot {slot.id} points to non-enchantment entity {entity!r}"
            )

        if not entity.active:
            raise RuntimeError(
                f"Slot {slot.id} points to inactive enchantment {entity.id}"
            )

        if entity.slot_id != slot.id:
            raise RuntimeError(
                f"Enchantment {entity.id} has slot_id={entity.slot_id}, "
                f"but is attached to slot {slot.id}"
            )

        return entity

    def active_enchantments(
        self,
        player: Player | PlayerId,
    ) -> list[Enchantment]:
        if isinstance(player, PlayerId):
            player = self.player(player)

        if not isinstance(player, Player):
            raise TypeError(
                f"Expected Player or PlayerId, got {type(player).__name__}"
            )

        result = []
        for slot in player.board_slots:
            enchantment = self.enchantment_on_slot(slot)
            if enchantment is not None:
                result.append(enchantment)

        return result

    def create_enchantment(
        self,
        enchantment_type: type[Enchantment],
        slot: BoardSlot,
        *,
        creator_id: int | None = None,
        creator_base_identity: BaseIdentity | None = None,
    ) -> Enchantment:
        if not isinstance(slot, BoardSlot):
            raise TypeError(
                f"Expected BoardSlot, got {type(slot).__name__}"
            )

        if not isinstance(enchantment_type, type):
            raise TypeError(
                f"Expected Enchantment class, got {type(enchantment_type).__name__}"
            )

        if not issubclass(enchantment_type, Enchantment):
            raise TypeError(
                f"Expected Enchantment class, got {enchantment_type!r}"
            )

        if slot.enchantment_id is not None:
            raise RuntimeError(
                f"Board slot {slot.id} is already enchanted"
            )

        new_enchantment = enchantment_type(
            id=self.alloc_entity_id(),
            controller_id=slot.controller_id,
            slot_id=slot.id,
            creator_id=creator_id,
            creator_base_identity=creator_base_identity,
        )

        self.register_entity(
            new_enchantment,
            entity_id=new_enchantment.id,
        )

        slot.enchantment_id = new_enchantment.id
        self.rules.invalidate()

        return new_enchantment

    def remove_enchantment(
        self,
        enchantment: Enchantment,
    ) -> bool:
        if not isinstance(enchantment, Enchantment):
            raise TypeError(
                f"Expected Enchantment, got {type(enchantment).__name__}"
            )

        if not enchantment.active:
            return False

        slot_entity = self.entity(enchantment.slot_id)
        if not isinstance(slot_entity, BoardSlot):
            raise RuntimeError(
                f"Enchantment {enchantment.id} points to a non-slot entity"
            )

        if slot_entity.enchantment_id != enchantment.id:
            raise RuntimeError(
                f"Slot/enchantment attachment mismatch for "
                f"enchantment {enchantment.id}"
            )

        slot_entity.enchantment_id = None
        enchantment.active = False

        self.rules.invalidate()
        return True

    # --------------------------
    # Target & choice filtering
    # --------------------------

    def _filter_player_choice_options(
        self,
        options: list[Entity],
        for_spell_targeting: bool = False,
    ) -> list[Entity]:
        """Apply rules for player-chosen selections (Choose effect / on-play targeting / attacks)"""
        res = []
        for x in options:
            if isinstance(x, Monster):
                if x.has_keyword(CardKeyword.TRANSPARENCY):
                    continue
                if for_spell_targeting and x.has_keyword(CardKeyword.DARKSPAWN):
                    continue

            res.append(x)

        return res

    @staticmethod
    def resolve_summon_position(
        controller: Player,
        pos: int | None,
    ) -> tuple[bool, int | None, str]:
        if pos is None:
            try:
                return True, controller.board.get_empty_slot_index(), 'ok'
            except StopIteration:
                return False, None, 'board_full'

        if not (0 <= pos < controller.board.MAX_CARDS):
            return False, None, 'invalid_slot'

        if controller.board[pos] is not None:
            return False, None, 'slot_occupied'

        return True, pos, 'ok'

    def play_target_options(self, card: Card, player: Player, pos: int | None = None) -> list[Entity]:
        """Evaluate `card.targets` into concrete selectable entities for on-play targeting."""
        selector = card.targets
        if selector is None:
            return []

        ctx = ActionContext(game=self, source=card)
        options = selector.eval(ctx=ctx, pos=pos, player=player)

        # Remove the card that's being played from available choices
        for index, x in enumerate(options):
            if x.id == card.id:
                del options[index]
                break

        return self._filter_player_choice_options(options, for_spell_targeting=isinstance(card, Spell))

    def can_play_from_hand(self, player: Player, card_id: int, pos: int | None = None) -> tuple[bool, str]:
        """Check if a player can play a card from their hand."""
        try:
            card = self.entity(card_id)
        except KeyError:
            return False, 'invalid_card_id'

        if not isinstance(card, Card):
            return False, 'invalid_card_id'

        if (card.zone is not CardZone.HAND) or (card.controller_id != player.id):
            return False, 'card_not_in_hand'

        if player.gold < card.cost:
            return False, 'insufficient_gold'

        if isinstance(card, Monster):
            ok, _, reason = self.resolve_summon_position(player, pos)
            return ok, reason

        # Spells: must have a valid target (if they require on-play targets)
        if isinstance(card, Spell):
            if card.targets is not None:
                if not self.play_target_options(card=card, player=player):
                    return False, 'no_available_targets'

            return True, 'ok'

        raise ValueError(f"Card is of invalid type {type(card)}")

    def can_attack(
        self,
        attacker_id: int,
        defender_id: int,
        initiated_by_player: Player | None = None,  # set only when attack is initiated directly by player input
    ) -> tuple[bool, str]:
        try:
            attacker = self.entity(attacker_id)
        except KeyError:
            return False, 'invalid_attacker_id'

        try:
            defender = self.entity(defender_id)
        except KeyError:
            return False, 'invalid_defender_id'

        if not isinstance(attacker, Monster):
            return False, 'invalid_attacker_id'

        if attacker.zone is not CardZone.BOARD:
            return False, 'attacker_not_on_board'

        if attacker.has_attacked:
            return False, 'already_attacked_this_turn'

        if attacker.has_keyword(CardKeyword.DISARMED):
            return False, 'cannot_attack'

        if attacker.get_status(CardStatusId.PARALYZED) > 0:
            return False, 'cannot_attack'

        if attacker.age == 0 and not (
            attacker.has_keyword(CardKeyword.CHARGE)
            or attacker.has_keyword(CardKeyword.HASTE)
        ):
            return False, 'cannot_attack'

        if isinstance(defender, Player):
            if attacker.has_keyword(CardKeyword.HASTE) and not attacker.has_keyword(CardKeyword.CHARGE):
                return False, 'cannot_attack'

        elif isinstance(defender, Monster):
            if defender.zone is not CardZone.BOARD:
                return False, 'defender_not_on_board'

        else:
            return False, 'invalid_defender_id'

        if initiated_by_player:
            if attacker.controller_id != initiated_by_player.id:
                return False, 'invalid_attacker_id'

            if isinstance(defender, Monster) and defender.has_keyword(CardKeyword.TRANSPARENCY):
                return False, 'invalid_defender_id'

            if defender.controller_id == attacker.controller_id:
                return False, 'invalid_defender_id'

            enemy_monsters = self._filter_player_choice_options(initiated_by_player.opponent.board.cards)
            taunts = [
                monster for monster in enemy_monsters
                if monster.has_keyword(CardKeyword.TAUNT)
            ]
            if taunts and (defender not in taunts):
                return False, 'invalid_defender_id'

        return True, 'ok'

    def _iter_event_sources_of_player(self, player: Player, board_only: bool = False):
        for card in player.board.cards:
            if not card.silenced:
                yield card

        if board_only:
            return

        yield from self.active_enchantments(player)

        yield player.soul

        for artifact in player.artifacts:
            if artifact.active:
                yield artifact

    def _iter_game_start_sources_of_player(self, player: Player):
        yield from self._iter_event_sources_of_player(player)

        yield from player.hand.cards
        yield from player.deck.cards

    def _iter_event_sources(self):
        for player in (self.turn_player, self.turn_player.opponent):
            yield from self._iter_event_sources_of_player(player)

    def _collect_result_handlers(self, res: ActionResult) -> list[tuple[Entity, Action]]:
        actions = []
        event_sources = list(self._iter_event_sources())

        if isinstance(res, AttackResolvedResult):
            # Attacker and defender should be able to handle `AttackResolvedResult` even if they left the board
            attacker = self.entity(res.attacker_id)
            if (not res.attacker.silenced) and (attacker not in event_sources):
                event_sources.append(attacker)

            defender = self.entity(res.defender_id)
            if (isinstance(defender, Player) or not res.defender.silenced) and (defender not in event_sources):
                event_sources.append(defender)

        for entity in event_sources:
            # Monster shouldn't receive `MonsterSummonedResult` and `CardPlayedResult` events on its own summon
            if (
                (isinstance(res, MonsterSummonedResult) and entity.id == res.monster_id)
                or (isinstance(res, CardPlayedResult) and entity.id == res.card_id)
            ):
                continue

            event_handlers = entity.post_event_handlers
            for res_class, event_handler in event_handlers.items():
                if isinstance(res, res_class):
                    actions_to_append = event_handler(entity, res, game=self)
                    if actions_to_append is not None:
                        actions.append((entity, actions_to_append))

        return actions

    def _record_action_results(self, results: Sequence[ActionResult]) -> list[tuple[Entity, Any]]:
        handlers: list[tuple[Entity, Any]] = []
        for r in results:
            r.id = self._next_action_result_id
            self._next_action_result_id += 1

            r.turn = self.turn
            r.turn_player_id = self.turn_player.id

            self.log.append(r)
            self.log_by_type.setdefault(type(r), []).append(r)

            handlers.extend(self._collect_result_handlers(r))

        return handlers

    def _eval_entities(self, x, ctx: ActionContext, **kwargs) -> list[Entity]:
        if x is None:
            return []

        if isinstance(x, Entity):
            return [x]

        if isinstance(x, (list, tuple)):
            res = []
            for i in x:
                res.extend(self._eval_entities(i, ctx=ctx, **kwargs))

            return res

        if isinstance(x, (TargetSelector, Var)):
            try:
                res = x.eval(ctx=ctx, **kwargs)
            except Exception as e:
                raise RuntimeError(f"Exception while trying to eval entity from {x!r}") from e

            if res is None:
                return []
            if isinstance(res, Entity):
                return [res]
            if isinstance(res, (list, tuple)):
                return list(res)

            raise TypeError(f"{x!r} evaluated to non-entity value: {res!r}")

        raise TypeError(f"Expected Entity/list/tuple/selector, got {type(x).__name__}: {x!r}")

    # --------------------
    # Ability listeners
    # --------------------

    def collect_ability_listener_effects(self, ability: Ability, player: Player, board_only: bool = False):
        for entity in self._iter_event_sources_of_player(player, board_only=board_only):
            effect = entity.get_ability(ability)
            if effect is None:
                continue

            yield effect, entity

    def collect_game_start_listener_effects(self, player: Player):
        for entity in self._iter_game_start_sources_of_player(player):
            effect = entity.get_ability(Ability.GAME_START)
            if effect is None:
                continue

            yield effect, entity

    def card_need_fulfilled(self, card: Card) -> bool:
        condition = card.get_need_condition()
        if condition is None:
            return False

        if card.has_keyword(CardKeyword.FLOWERY_POWER):
            return True

        return bool(
            evaluate_expr(
                condition,
                ctx=ActionContext(game=self, source=card),
            )
        )

    # --------------------
    # Scheduled effects
    # --------------------

    def schedule_effect(self, entity_id: int, name: str, ctx: ActionContext) -> None:
        self.scheduled_effects.append(
            ScheduledEffect(
                entity_id=entity_id,
                name=name,
                env=ctx.env.copy(),
                vars=ctx.vars.copy(),
            )
        )

    # --------------------
    # Effect Queue API
    # --------------------

    def enqueue_actions(
        self,
        actions: Action | list[Action] | tuple[Action] | EffectBase | Callable | Generator | None,
        *,
        source: Entity,
        env: dict[str, Any] | None = None,
        ctx: ActionContext | None = None,
        log_group_id: int | None = None,
        log_parent_id: int | None = None,
        log_depth: int = 0,
        **kwargs,
    ) -> None:
        if actions is None:
            return

        if log_group_id is None:
            log_group_id = self.alloc_action_log_group_id()

        if isinstance(actions, (list, tuple)):
            for action in reversed(actions):
                self.enqueue_actions(
                    action,
                    source=source,
                    env=env,
                    ctx=ctx,
                    log_group_id=log_group_id,
                    log_parent_id=log_parent_id,
                    log_depth=log_depth,
                    **kwargs,
                )

            return

        pending = PendingAction(
            action=actions,
            source=source,
            kwargs=kwargs.copy(),
            env=dict(env or {}),
            ctx=ctx,
            log_group_id=log_group_id,
            log_parent_id=log_parent_id,
            log_depth=log_depth,
        )
        self.resolution_stack.append(pending)

    # --------------------
    # Effect resolution
    # --------------------

    def _schedule_effect_step(
        self,
        generator: Generator,
        base_pending: PendingAction,
        ctx: ActionContext,
        step: EffectStep,
    ) -> None:
        items = step.items
        step_kwargs = step.kwargs.copy()

        resume_pending = PendingAction(
            action=generator,
            source=base_pending.source,
            kwargs=step_kwargs,
            env=base_pending.env.copy(),
            ctx=ctx,
            send_value=None,

            # Preserve parent group if this generator/effect is itself being
            # awaited by an outer generator/effect.
            step_group_id=base_pending.step_group_id,

            log_group_id=base_pending.log_group_id,
            log_parent_id=base_pending.log_parent_id,
            log_depth=base_pending.log_depth,
        )

        if not items:
            # If step contains no items, immediately resume with an empty success list.
            resume_pending.send_value = StepResult([])
            self.resolution_stack.append(resume_pending)
            return

        group_id = self._next_step_group_id
        self._next_step_group_id += 1

        self._step_groups[group_id] = StepGroup(
            waiting_coroutine=resume_pending,
            remaining=len(items),
            successes=[],
        )

        pendings = [
            PendingAction(
                action=item,
                source=base_pending.source,
                kwargs=step_kwargs,
                env=base_pending.env.copy(),
                ctx=ctx,
                send_value=None,
                step_group_id=group_id,
                log_group_id=base_pending.log_group_id,
                log_parent_id=base_pending.log_parent_id,
                log_depth=base_pending.log_depth,
            )
            for item in items
        ]

        for pending in reversed([*pendings, resume_pending]):
            self.resolution_stack.append(pending)

    def _finish_step_action(
        self,
        pending: PendingAction,
        success: bool,
        results: Sequence[ActionResult] = (),
    ) -> None:
        group_id = pending.step_group_id
        if group_id is None:
            return

        group = self._step_groups[group_id]
        group.remaining -= 1
        group.successes.append(success)
        group.results.extend(results)

        if group.remaining == 0:
            # Exit the step group and return result to the waiting coroutine
            group.waiting_coroutine.send_value = StepResult(group.successes, tuple(group.results))
            del self._step_groups[group_id]

        elif group.remaining < 0:
            raise RuntimeError(f"`StepGroup.remaining` became negative for {group_id=}")

    def _maybe_expand_many_arg(self, pending: PendingAction, ctx: ActionContext) -> bool:
        """
        If pending.action has a many=True arg that isn't bound yet, expand it.

        Returns True if expansion was performed (even if it produced zero entities).
        """
        action = pending.action
        if (not isinstance(action, Action)) or (not action.many_arg_names):
            return False

        if len(action.many_arg_names) != 1:
            raise NotImplementedError("Only one `many` arg is supported currently")

        many_arg_name = action.many_arg_names[0]

        # If already bound, do not expand.
        if many_arg_name in pending.kwargs and isinstance(pending.kwargs[many_arg_name], Entity):
            return False

        # Spec to expand: override in kwargs takes precedence, otherwise, use action's expr.
        spec = pending.kwargs.get(many_arg_name, getattr(action, many_arg_name))

        # If the expression is already a single concrete entity, expansion is not needed.
        if isinstance(spec, Entity):
            return False

        # Only expand if it is something that can yield entities.
        if spec is not None and not isinstance(spec, (list, tuple, TargetSelector, Var)):
            return False

        targets = self._eval_entities(spec, ctx=ctx, **pending.kwargs)

        # If expansion produced no targets, fizzle this action.
        if not targets:
            self._finish_step_action(pending, success=False, results=())
            return True

        # Replace 1 pending with N pending and update StepGroup's `remaining` count.
        if pending.step_group_id is not None:
            group = self._step_groups[pending.step_group_id]
            group.remaining += (len(targets) - 1)

        # Enqueue expanded actions.
        for target in reversed(targets):
            new_kwargs = pending.kwargs.copy()
            new_kwargs[many_arg_name] = target

            self.resolution_stack.append(
                PendingAction(
                    action=action,
                    source=pending.source,
                    kwargs=new_kwargs,
                    env=pending.env,
                    ctx=ctx,
                    send_value=None,
                    step_group_id=pending.step_group_id,
                    log_group_id=pending.log_group_id,
                    log_parent_id=pending.log_parent_id,
                    log_depth=pending.log_depth,
                )
            )

        return True

    def _coerce_generator_yield(self, yielded: object, pending: PendingAction) -> EffectStep:
        if isinstance(yielded, EffectStep):
            return yielded

        if isinstance(yielded, (Action, EffectBase)):
            return EffectStep([yielded], kwargs=pending.kwargs.copy())

        raise TypeError(
            'Custom effect generators may only yield Action, EffectBase, or EffectStep; '
            f'got {type(yielded).__name__}: {yielded!r}'
        )

    def _generator_return_to_step_results(self, value: Any) -> tuple[bool, tuple[ActionResult, ...]]:
        """
        Convert a finished generator/effect return value into the success/results
        reported to the parent StepGroup.

        Normal custom generators usually return None.
        EffectBase generators return EffectResult.
        """
        if isinstance(value, (EffectResult, StepResult)):
            return value.success, value.results

        if isinstance(value, bool):
            return value, ()

        return True, ()

    def _resolve_generator(self, pending: PendingAction, ctx: ActionContext) -> list[ActionResult]:
        generator = pending.action
        if not isinstance(generator, types.GeneratorType):
            raise TypeError(f'Expected a generator, got {type(generator).__name__}: {generator!r}')

        send_value = pending.send_value
        pending.send_value = None

        try:
            yielded = generator.send(send_value) if send_value is not None else next(generator)

        except StopIteration as stop:
            if pending.step_group_id is not None:
                success, results = self._generator_return_to_step_results(stop.value)
                self._finish_step_action(pending, success=success, results=results)

            return []

        except Exception as e:
            # Attempt to restore an effect associated to the generator
            tb = e.__traceback__
            while tb is not None:
                if tb.tb_frame.f_code is generator.gi_code:
                    effect = tb.tb_frame.f_locals.get('self')
                    raise RuntimeError(f"Exception while resolving {effect!r}") from e

                tb = tb.tb_next

        # Custom generators use the same step/resume protocol as `EffectBase`:
        # every `yield` statement represents exactly one step and receives `StepResult` on resume.
        self._schedule_effect_step(
            generator=generator,
            base_pending=pending,
            ctx=ctx,
            step=self._coerce_generator_yield(yielded, pending),
        )
        return []

    def _enqueue_effect_calls(
        self,
        effects: Sequence[tuple[Entity, Any]],
        *,
        env: dict[str, Any],
        log_group_id: int,
        log_parent_id: int,
        log_depth: int,
    ) -> None:
        for entity, effect in reversed(effects):
            self.enqueue_actions(
                effect,
                source=entity,
                env=env.copy(),
                ctx=None,
                log_group_id=log_group_id,
                log_parent_id=log_parent_id,
                log_depth=log_depth,
            )

    def _enqueue_action_calls(
        self,
        action_calls: Sequence[ActionCall],
        *,
        env: dict[str, Any],
        log_group_id: int,
        log_parent_id: int,
        log_depth: int,
    ) -> None:
        for call in reversed(action_calls):
            merged_env = env.copy()
            merged_env.update(call.env)

            self.enqueue_actions(
                call.action,
                source=call.source,
                env=merged_env,
                ctx=ActionContext(game=self, source=call.source, vars=call.vars),
                log_group_id=log_group_id,
                log_parent_id=log_parent_id,
                log_depth=log_depth,
                **call.kwargs,
            )

    def _resolve_one(self, pending: PendingAction) -> list[ActionResult]:
        action = pending.action
        source = pending.source
        ctx = pending.ctx

        if ctx is None:
            ctx = ActionContext(game=self, source=source)
            pending.ctx = ctx

        ctx.env = pending.env

        if isinstance(action, EffectBase):
            generator = action(ctx=ctx, **pending.kwargs)
            pending.action = generator
            return self._resolve_generator(pending, ctx=ctx)

        if isinstance(action, types.GeneratorType):
            return self._resolve_generator(pending, ctx=ctx)

        if isinstance(action, Action):
            return self._resolve_atomic_action(pending, ctx=ctx)

        if callable(action):
            actions = evaluate_expr(action, ctx=ctx, **pending.kwargs)
            self.enqueue_actions(
                actions,
                source=pending.source,
                ctx=ctx,
                env=pending.env,
                log_group_id=pending.log_group_id,
                log_parent_id=pending.log_parent_id,
                log_depth=pending.log_depth,
                **pending.kwargs,
            )
            return []

        raise TypeError(f'Item in resolution stack is of invalid type {type(action).__name__}: {action!r}')

    def _handle_state_based_actions(self) -> None:
        for p in self.players.values():
            for m in p.board.cards:
                if m.hp <= 0 and not m.marked_for_destruction:
                    # print(f"Clamp hp for {m}: {m.hp} => 1")
                    m.buff(hp=1 - m.hp)

    # -------------------------
    # Atomic Action resolution
    # -------------------------

    def _resolve_atomic_action(self, pending: PendingAction, ctx: ActionContext) -> list[ActionResult]:
        action = pending.action

        # Perform expansion for args with `many=True`.
        if self._maybe_expand_many_arg(pending, ctx=ctx):
            return []

        # Resolve args for `action.execute()`.
        # Expand selectors, variables and other expressions into concrete values.
        try:
            resolved_args = action.resolve(ctx, **pending.kwargs)
        except NoTargetsError:
            # If there are no targets, fizzle this action.
            self._finish_step_action(pending, success=False, results=())
            return []

        if pending.log_group_id is None:
            pending.log_group_id = self.alloc_action_log_group_id()

        # Execute the atomic action
        res = action.execute(ctx=ctx, **resolved_args)
        if not isinstance(res, ActionOutcome):
            raise TypeError(f'{type(action).__name__}.execute() must return ActionOutcome, got {type(res).__name__}')

        action_log_id = self.alloc_action_log_id()
        self.action_log.append(
            ActionLogRecord(
                id=action_log_id,
                action_name=type(action).__name__,
                results=tuple(res.results),
                group_id=pending.log_group_id,
                parent_id=pending.log_parent_id,
                depth=pending.log_depth,
                source_id=pending.source.id,
                affected_ids=tuple(entity.id for entity in (res.affected or ())),
                presentation_results=(
                    tuple(res.presentation_results)
                    if res.presentation_results is not None
                    else None
                ),
            )
        )

        # If this atomic action belonged to a `StepGroup`, update its state.
        self._finish_step_action(pending, success=res.success, results=res.results)

        # If this atomic action produced a pending request, pause the engine until a response is provided.
        if res.pending_request is not None:
            assert not res.results
            assert not res.action_calls

            req = res.pending_request
            req.source_id = pending.source.id
            self.pending_requests[req.request_id] = req
            return list(res.results)

        # Enqueue action-requested follow-ups & triggers.
        if res.action_calls:
            self._enqueue_action_calls(
                res.action_calls,
                env=pending.env,
                log_group_id=pending.log_group_id,
                log_parent_id=action_log_id,
                log_depth=pending.log_depth + 1,
            )

        # Run handlers that should run right after the atomic action resolves (e.g. "after this attacks, do ...").
        result_handlers = self._record_action_results(res.results)
        if result_handlers:
            self._enqueue_effect_calls(
                result_handlers,
                env=pending.env,
                log_group_id=pending.log_group_id,
                log_parent_id=action_log_id,
                log_depth=pending.log_depth + 1,
            )

        # Handle state-based actions after every atomic action resolution.
        self._handle_state_based_actions()

        return list(res.results)

    # --------------------
    # Replacement effects
    # --------------------

    def check_death_prevented(
        self,
        target: Monster | Player,
        killer: Entity,
        *,
        cause: KillCause = KillCause.OTHER,
    ) -> tuple[bool, list[ActionCall]]:
        death_prevented = False
        extra_actions = []

        for entity in self._iter_event_sources():
            if getattr(entity, 'on_would_die', None) is not None:
                replacement_effects = entity.on_would_die(target, game=self)
                if replacement_effects:
                    death_prevented = True
                    extra_actions.append(
                        ActionCall(
                            replacement_effects,
                            source=entity,
                        )
                    )
                    break

        if not death_prevented:
            extra_actions.append(
                ActionCall(
                    Kill(
                        target=target,
                        killer=killer,
                        skip_check_death_prevented=True,
                        cause=cause,
                    ),
                    source=killer,
                )
            )

        if isinstance(target, Monster):
            # Monsters are marked for destruction even if their death was prevented.
            # This flag must be set back to False by a death replacement effect later.
            target.marked_for_destruction = True

        return death_prevented, extra_actions

    def check_overdraw_prevented(self, player: Player) -> tuple[bool, list[ActionCall]]:
        for entity in self._iter_event_sources():
            if getattr(entity, 'on_would_overdraw', None) is not None:
                replacement_effects = entity.on_would_overdraw(player, game=self)
                if replacement_effects:
                    return True, [ActionCall(replacement_effects, source=entity)]

        return False, []

    # --------------------
    # Damage
    # --------------------

    def apply_damage(
        self,
        target: Monster | Player,
        damage: int,
        source: Entity,
        kind: DamageKind | None,
        *,
        combat_attacker: Monster | None = None,
        combat_defender: Entity | None = None,
    ) -> DamageApplyResult:
        if damage <= 0:
            return DamageApplyResult(prevented_by='zero')

        if kind is None:
            if isinstance(source, Spell):
                kind = DamageKind.SPELL
            else:
                kind = DamageKind.ABILITY

        if not isinstance(target, (Monster, Player)):
            return DamageApplyResult(prevented_by='invalid_target')

        if isinstance(target, Monster):
            if target.marked_for_destruction:
                return DamageApplyResult(prevented_by='invalid_target')

            if target.zone is not CardZone.BOARD:
                return DamageApplyResult(prevented_by='invalid_target')

            if target.has_keyword(CardKeyword.INVULNERABLE):
                return DamageApplyResult(prevented_by='invulnerable')

            if target.has_keyword(CardKeyword.DARKSPAWN) and isinstance(source, Spell):
                return DamageApplyResult(prevented_by='darkspawn')

        q = DamageQuery(
            game=self,
            source=source,
            target=target,
            amount=damage,
            kind=kind,
            combat_attacker=combat_attacker,
            combat_defender=combat_defender,
        )
        damage = self.rules.damage(q)

        if isinstance(target, Monster) and target.has_keyword(CardKeyword.ARMOR):
            damage -= 1

        if damage <= 0:
            return DamageApplyResult(prevented_by='reduced_to_zero')

        if isinstance(target, Player):
            target.hp = target.hp - damage

            if target.hp <= 0:
                death_prevented, extra_actions = self.check_death_prevented(
                    target,
                    source,
                    cause=(
                        KillCause.COMBAT
                        if kind is DamageKind.COMBAT
                        else KillCause.DAMAGE_EFFECT
                    ),
                )
            else:
                death_prevented = False
                extra_actions = []

            killed = target.hp <= 0 and not death_prevented

            return DamageApplyResult(
                damage=damage,
                killed=killed,
                results=[
                    EntityDamagedResult(
                        source_id=source.id,
                        target_id=target.id,
                        target=target.to_snapshot(),
                        amount=damage,
                        killed=killed,
                        excess_damage=0,
                        kind=kind,
                    ),
                ],
                extra_actions=extra_actions,
            )

        dodge_counters = target.get_status(CardStatusId.DODGE)
        if dodge_counters >= 1:
            target.set_status(CardStatusId.DODGE, dodge_counters - 1)
            return DamageApplyResult(
                prevented_by='dodge',
                results=[
                    DodgeConsumedResult(
                        source_id=source.id,
                        monster_id=target.id,
                        monster=target.to_snapshot(),
                    ),
                ],
            )

        hp_before = target.hp
        target.hp_missing += damage
        excess_damage = max(damage - hp_before, 0)

        if target.hp <= 0:
            death_prevented, extra_actions = self.check_death_prevented(
                target,
                source,
                cause=(
                    KillCause.COMBAT
                    if kind is DamageKind.COMBAT
                    else KillCause.DAMAGE_EFFECT
                ),
            )
        else:
            death_prevented = False
            extra_actions = []

        killed = target.hp <= 0 and not death_prevented
        damage_result = EntityDamagedResult(
            source_id=source.id,
            target_id=target.id,
            target=target.to_snapshot(),
            amount=damage,
            killed=killed,
            excess_damage=excess_damage,
            kind=kind,
        )

        # Bullseye: If this entity brings a monster to exactly 0 HP, trigger this effect.
        if killed and excess_damage == 0:
            effect = source.get_ability(Ability.BULLSEYE)
            if effect is not None:
                if isinstance(source, Monster):
                    self.hold_monster_death_finalization(source)

                extra_actions.append(
                    ActionCall(
                        TriggerAbility(target=source, ability=Ability.BULLSEYE),
                        source=source,
                        env={'target': target.to_snapshot(), 'result': damage_result},
                    )
                )

                if isinstance(source, Monster):
                    extra_actions.append(
                        ActionCall(
                            ReleaseMonsterDeathFinalization(target=source),
                            source=source,
                        )
                    )

        self.rules.invalidate()

        return DamageApplyResult(
            damage=damage,
            excess_damage=excess_damage,
            killed=killed,
            results=[damage_result],
            extra_actions=extra_actions,
        )

    # --------------------
    # Debug
    # --------------------

    def check_invariants(self) -> None:
        """Check that the game state is consistent (for debug)."""

        seen_cards: dict[int, str] = {}

        def _register(
            c: Card,
            *,
            location: str,
            expected_zone: CardZone | None,
            expected_controller: PlayerId | None,
            expected_pos: int | None = None,
        ) -> None:
            assert c is not None, f"{location}: card is None"
            assert isinstance(c, Card), f"{location}: expected Card, got {type(c).__name__}"

            # Each card must appear only in one of the zones
            if c.id in seen_cards:
                raise AssertionError(f"Card id {c.id} appears twice: {seen_cards[c.id]} and {location}")

            seen_cards[c.id] = location

            # Zone must match container
            if expected_zone is not None:
                assert c.zone is expected_zone, (
                    f"{location}: card.zone mismatch: expected {expected_zone}, got {c.zone}"
                )

            # Controller must match container's owning player
            if expected_controller is not None:
                assert c.controller_id == expected_controller, (
                    f"{location}: card.controller_id mismatch: expected {expected_controller}, got {c.controller_id}"
                )

            # Board position invariants
            if isinstance(c, Monster):
                if expected_zone == CardZone.BOARD:
                    assert expected_pos is not None
                    assert c.pos == expected_pos, (
                        f"{location}: card.pos mismatch: expected {expected_pos}, got {c.pos}"
                    )
                else:
                    assert c.pos is None, (
                        f"{location}: non-board card has pos={c.pos} (zone={c.zone})"
                    )

        def _check_container(p: Player, attr_name: str, expected_zone: CardZone) -> None:
            container = getattr(p, attr_name)
            for i, c in enumerate(container.cards):
                if attr_name == 'dustpile':
                    assert isinstance(c, Monster), (
                        f"P{player.id.value}'s dustpile: expected Monster, got {type(c).__name__}"
                    )

                _register(
                    c,
                    location=f'P{p.id.value}.{attr_name}[{i}]',
                    expected_zone=expected_zone,
                    expected_controller=p.id,
                    expected_pos=None,
                )

        for player in self.players.values():
            _check_container(player, 'hand', CardZone.HAND)
            _check_container(player, 'deck', CardZone.DECK)
            _check_container(player, 'dustpile', CardZone.DUSTPILE)
            _check_container(player, 'erased', CardZone.ERASED)

            for pos, c in enumerate(player.board._cards):
                if c is None:
                    continue

                assert isinstance(c, Monster), f"P{player.id.value}'s board: expected Monster, got {type(c).__name__}"
                _register(
                    c,
                    location=f'P{player.id.value}.board[{pos}]',
                    expected_zone=CardZone.BOARD,
                    expected_controller=player.id,
                    expected_pos=pos,
                )

            for pos, slot in enumerate(player.board_slots):
                assert isinstance(slot, BoardSlot)
                assert slot.controller_id == player.id
                assert slot.owner_id == player.id
                assert slot.pos == pos
                assert self.entity(slot.id) is slot

                board_monster = player.board[pos]
                expected_monster_id = (
                    board_monster.id
                    if board_monster is not None
                    else None
                )
                assert slot.monster_id == expected_monster_id, (
                    f"P{player.id.value} slot {pos + 1}: "
                    f"slot.monster_id={slot.monster_id}, "
                    f"board monster={expected_monster_id}"
                )

                if slot.enchantment_id is not None:
                    enchantment = self.entity(slot.enchantment_id)
                    assert isinstance(enchantment, Enchantment)
                    assert enchantment.active
                    assert enchantment.slot_id == slot.id
                    assert enchantment.controller_id == player.id

        for entity in self.entities.values():
            if isinstance(entity, Enchantment):
                slot = self.entity(entity.slot_id)
                assert isinstance(slot, BoardSlot)

                if entity.active:
                    assert slot.enchantment_id == entity.id
                else:
                    assert slot.enchantment_id != entity.id

        for index, c in enumerate(self.stack):
            _register(
                c,
                location=f'stack[{index}]',
                expected_zone=CardZone.STACK,
                expected_controller=None,
                expected_pos=None,
            )

        if len(self.resolution_stack) == 0:
            assert self._step_groups == {}

        for pending in self.resolution_stack:
            if pending.step_group_id is not None:
                assert pending.step_group_id in self._step_groups

        for group_id, group in self._step_groups.items():
            assert group.remaining >= 0
