from dataclasses import dataclass
from typing import ClassVar

from deltacards.model.enums import Ability, DamageKind, KillCause, PlayerId
from deltacards.model.snapshots import (
    BoardSlotSnapshot,
    CardSnapshot,
    EnchantmentSnapshot,
    EntitySnapshot,
    MonsterSnapshot,
    PlayerSnapshot,
)
from deltacards.model.types import EnchantmentRemovalReason, GoldSpendReason

__all__ = (
    'ActionResult',
    'CardRevealedResult',
    'CardDrawnResult',
    'CardOverdrawnResult',
    'EntityDamagedResult',
    'EntityHealedResult',
    'DodgeConsumedResult',
    'AttackDeclaredResult',
    'AttackResolvedResult',
    'MonsterSummonedResult',
    'CardPlayedResult',
    'SpellCastResult',
    'MonsterKilledResult',
    'PlayerDefeatedResult',
    'GoldSpentResult',
    'AbilityTriggeredResult',
    'EventReactionTriggeredResult',
    'BoardSlotEnchantedResult',
    'EnchantmentRemovedResult',
)


@dataclass(slots=True, kw_only=True)
class ActionResult:
    # Filled by Game when recorded
    id: int = -1
    turn: int = -1
    turn_player_id: PlayerId = -1

    source_id: PlayerId | int | None = None
    group_id: int | None = None

    # History metadata
    history_subject_attr: ClassVar[str | None] = None
    history_player_id_attr: ClassVar[str | None] = None
    history_card_id_attr: ClassVar[str | None] = None
    history_target_id_attr: ClassVar[str | None] = None
    history_killer_id_attr: ClassVar[str | None] = None
    history_attacker_id_attr: ClassVar[str | None] = None
    history_defender_id_attr: ClassVar[str | None] = None

    @property
    def history_subject(self):
        if self.history_subject_attr is None:
            return None

        return getattr(self, self.history_subject_attr)

    @property
    def history_player_id(self) -> PlayerId | None:
        if self.history_player_id_attr is None:
            return None

        return getattr(self, self.history_player_id_attr)

    @property
    def history_card_id(self) -> int | None:
        if self.history_card_id_attr is None:
            return None

        return getattr(self, self.history_card_id_attr)

    @property
    def history_target_id(self) -> PlayerId | int | None:
        if self.history_target_id_attr is None:
            return None

        return getattr(self, self.history_target_id_attr)

    @property
    def history_killer_id(self) -> PlayerId | int | None:
        if self.history_killer_id_attr is None:
            return None

        return getattr(self, self.history_killer_id_attr)

    @property
    def history_attacker_id(self) -> int | None:
        if self.history_attacker_id_attr is None:
            return None

        return getattr(self, self.history_attacker_id_attr)

    @property
    def history_defender_id(self) -> PlayerId | int | None:
        if self.history_defender_id_attr is None:
            return None

        return getattr(self, self.history_defender_id_attr)


@dataclass(slots=True, kw_only=True)
class CardRevealedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'card'
    history_card_id_attr: ClassVar[str | None] = 'card_id'

    card_id: int
    card: CardSnapshot


@dataclass(slots=True, kw_only=True)
class CardDrawnResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'card'
    history_player_id_attr: ClassVar[str | None] = 'player_id'
    history_card_id_attr: ClassVar[str | None] = 'card_id'

    player_id: PlayerId
    card_id: int
    card: CardSnapshot
    reason: str


@dataclass(slots=True, kw_only=True)
class CardOverdrawnResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'card'
    history_player_id_attr: ClassVar[str | None] = 'player_id'
    history_card_id_attr: ClassVar[str | None] = 'card_id'

    player_id: PlayerId
    card_id: int
    card: CardSnapshot


@dataclass(slots=True, kw_only=True)
class EntityDamagedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'target'
    history_target_id_attr: ClassVar[str | None] = 'target_id'

    target_id: PlayerId | int
    target: MonsterSnapshot | PlayerSnapshot
    amount: int
    killed: bool
    excess_damage: int
    kind: DamageKind


@dataclass(slots=True, kw_only=True)
class EntityHealedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'target'
    history_target_id_attr: ClassVar[str | None] = 'target_id'

    target_id: PlayerId | int
    target: MonsterSnapshot | PlayerSnapshot
    amount: int


@dataclass(slots=True, kw_only=True)
class DodgeConsumedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'monster'
    history_target_id_attr: ClassVar[str | None] = 'monster_id'

    monster_id: int
    monster: MonsterSnapshot


@dataclass(slots=True, kw_only=True)
class AttackDeclaredResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'attacker'
    history_target_id_attr: ClassVar[str | None] = 'defender_id'
    history_attacker_id_attr: ClassVar[str | None] = 'attacker_id'
    history_defender_id_attr: ClassVar[str | None] = 'defender_id'

    attacker_id: int
    attacker: MonsterSnapshot
    defender_id: PlayerId | int
    defender: MonsterSnapshot | PlayerSnapshot


@dataclass(slots=True, kw_only=True)
class AttackResolvedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'attacker'
    history_target_id_attr: ClassVar[str | None] = 'defender_id'
    history_attacker_id_attr: ClassVar[str | None] = 'attacker_id'
    history_defender_id_attr: ClassVar[str | None] = 'defender_id'

    attacker_id: int
    attacker: MonsterSnapshot
    defender_id: PlayerId | int
    defender: MonsterSnapshot | PlayerSnapshot

    damage_to_attacker: int
    damage_to_defender: int

    attacker_dead: bool
    defender_dead: bool


@dataclass(slots=True, kw_only=True)
class MonsterSummonedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'monster'
    history_player_id_attr: ClassVar[str | None] = 'player_id'
    history_card_id_attr: ClassVar[str | None] = 'monster_id'

    player_id: PlayerId
    monster_id: int
    monster: MonsterSnapshot
    target: EntitySnapshot | None
    is_played: bool


@dataclass(slots=True, kw_only=True)
class SpellCastResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'card'
    history_player_id_attr: ClassVar[str | None] = 'player_id'
    history_card_id_attr: ClassVar[str | None] = 'card_id'

    player_id: PlayerId
    card_id: int
    card: CardSnapshot
    target: EntitySnapshot | None
    is_played: bool


@dataclass(slots=True, kw_only=True)
class CardPlayedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'card'
    history_player_id_attr: ClassVar[str | None] = 'player_id'
    history_card_id_attr: ClassVar[str | None] = 'card_id'

    player_id: PlayerId
    card_id: int
    card: CardSnapshot
    has_need_condition: bool = False
    need_fulfilled: bool = False


@dataclass(slots=True, kw_only=True)
class MonsterKilledResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'monster'
    history_card_id_attr: ClassVar[str | None] = 'monster_id'
    history_target_id_attr: ClassVar[str | None] = 'monster_id'
    history_killer_id_attr: ClassVar[str | None] = 'killer_id'

    monster_id: int
    monster: MonsterSnapshot
    killer_id: int
    killer: EntitySnapshot
    cause: KillCause = KillCause.OTHER


@dataclass(slots=True, kw_only=True)
class PlayerDefeatedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'player'
    history_target_id_attr: ClassVar[str | None] = 'player_id'
    history_killer_id_attr: ClassVar[str | None] = 'killer_id'

    player_id: PlayerId
    player: PlayerSnapshot
    killer_id: int
    killer: EntitySnapshot


@dataclass(slots=True, kw_only=True)
class GoldSpentResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'card'
    history_player_id_attr: ClassVar[str | None] = 'player_id'

    player_id: PlayerId
    amount: int
    reason: GoldSpendReason
    card: CardSnapshot | None
    is_generated: bool


@dataclass(slots=True, kw_only=True)
class AbilityTriggeredResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'entity'
    history_target_id_attr: ClassVar[str | None] = 'entity_id'

    entity_id: PlayerId | int
    entity: EntitySnapshot
    ability: Ability


@dataclass(slots=True, kw_only=True)
class EventReactionTriggeredResult(ActionResult):
    """Action-log-only presentation marker for effects returned by an event handler."""

    entity_id: PlayerId | int
    entity: EntitySnapshot


@dataclass(slots=True, kw_only=True)
class BoardSlotEnchantedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'enchantment'
    history_player_id_attr: ClassVar[str | None] = 'player_id'
    history_target_id_attr: ClassVar[str | None] = 'slot_id'

    player_id: PlayerId
    slot_id: int
    slot: BoardSlotSnapshot
    enchantment_id: int
    enchantment: EnchantmentSnapshot
    replaced_enchantment: EnchantmentSnapshot | None


@dataclass(slots=True, kw_only=True)
class EnchantmentRemovedResult(ActionResult):
    history_subject_attr: ClassVar[str | None] = 'enchantment'
    history_player_id_attr: ClassVar[str | None] = 'player_id'
    history_target_id_attr: ClassVar[str | None] = 'slot_id'

    player_id: PlayerId
    slot_id: int
    slot: BoardSlotSnapshot
    enchantment_id: int
    enchantment: EnchantmentSnapshot
    reason: EnchantmentRemovalReason
