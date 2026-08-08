from dataclasses import dataclass
from typing import TYPE_CHECKING

from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardToggleableAbility,
    CardType,
    Expansion,
    Tribe,
)
from deltacards.model.types import BaseIdentity

if TYPE_CHECKING:
    from deltacards.content.registry import ImageSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class CardTemplate:
    id: int
    name: str
    image: 'ImageSpec'
    rarity: CardRarity
    cost: int
    abilities: frozenset[Ability]
    keywords: CardKeyword
    statuses: dict[CardStatusId, int]
    active_abilities: set[CardToggleableAbility]
    expansion: Expansion
    tribes: tuple[Tribe, ...]
    soul_id: str | None

    @property
    def base_identity(self) -> BaseIdentity:
        return 'card', self.id

    @property
    def type(self) -> CardType:
        raise NotImplementedError

    def has_ability(self, ability: Ability) -> bool:
        return ability in self.abilities

    def has_keyword(self, keyword: CardKeyword) -> bool:
        return keyword in self.keywords

    def get_status(self, status_id: CardStatusId) -> int:
        return self.statuses.get(status_id, 0)

    def has_tribe(self, tribe: Tribe) -> bool:
        return (tribe in self.tribes) or (Tribe.ALL in self.tribes)


@dataclass(frozen=True, slots=True, kw_only=True)
class MonsterTemplate(CardTemplate):
    attack: int
    hp: int

    @property
    def type(self) -> CardType:
        return CardType.MONSTER


@dataclass(frozen=True, slots=True, kw_only=True)
class SpellTemplate(CardTemplate):
    @property
    def type(self) -> CardType:
        return CardType.SPELL
