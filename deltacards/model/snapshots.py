from dataclasses import dataclass
from typing import TYPE_CHECKING

from deltacards.model.enums import CardKeyword, CardStatusId, CardToggleableAbility, CardType, CardZone, PlayerId, Tribe
from deltacards.model.types import BaseIdentity

if TYPE_CHECKING:
    from deltacards.model.cards import BaseStats, CardBuffs, CardTemplate, CaughtCardData


@dataclass(frozen=True, slots=True, kw_only=True)
class EntitySnapshot:
    id: PlayerId | int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerSnapshot(EntitySnapshot):
    id: PlayerId
    gold: int
    hp: int
    max_hp: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CardSnapshot(EntitySnapshot):
    id: int
    type: CardType
    template: 'CardTemplate'
    controller_id: PlayerId
    base: BaseStats
    keywords: CardKeyword
    statuses: dict[CardStatusId, int]
    active_abilities: set[CardToggleableAbility]
    buffs: 'CardBuffs'
    caught_card: 'CaughtCardData | None'

    zone: CardZone
    creator_id: int | None
    creator_base_identity: BaseIdentity | None
    cost: int

    @property
    def is_generated(self) -> bool:
        return self.creator_id is not None

    @property
    def silenced(self) -> bool:
        return False

    def has_keyword(self, keyword: CardKeyword) -> bool:
        return keyword in self.keywords

    def get_status(self, status_id: CardStatusId) -> int:
        return self.statuses.get(status_id, 0)

    def has_tribe(self, tribe: Tribe) -> bool:
        return (tribe in self.template.tribes) or (Tribe.ALL in self.template.tribes)


@dataclass(frozen=True, slots=True, kw_only=True)
class MonsterSnapshot(CardSnapshot):
    age: int
    has_attacked: bool
    hp_missing: int

    slot_id: int | None
    pos: int | None

    attack: int
    hp: int
    max_hp: int

    @property
    def silenced(self) -> bool:
        return self.has_keyword(CardKeyword.SILENCED)


@dataclass(frozen=True, slots=True, kw_only=True)
class SpellSnapshot(CardSnapshot):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class SoulSnapshot(EntitySnapshot):
    id: int
    definition_id: str
    name: str
    controller_id: PlayerId


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactSnapshot(EntitySnapshot):
    id: int
    definition_id: int
    name: str
    controller_id: PlayerId
    counter: int
    active: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class BoardSlotSnapshot(EntitySnapshot):
    id: int
    controller_id: PlayerId
    pos: int

    monster_id: int | None
    enchantment_id: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EnchantmentSnapshot(EntitySnapshot):
    id: int
    definition_id: str
    name: str
    controller_id: PlayerId
    slot_id: int
    counter: int
    active: bool

    creator_id: int | None
    creator_base_identity: BaseIdentity | None
