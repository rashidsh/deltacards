from dataclasses import dataclass
from typing import TYPE_CHECKING

from deltacards.actions.results import MonsterKilledResult
from deltacards.content.registry import is_custom_content
from deltacards.dsl.core import Predicate, TargetSelector
from deltacards.dsl.inspection import (
    attr_of,
    card_type_of,
    expansion_of,
    generated_of,
    has_ability,
    has_keyword,
    has_tribe,
    status_of,
    tribes_of,
)
from deltacards.dsl.values import RARITY
from deltacards.model.cards import Card, CardBuffs
from deltacards.model.enchantments import ENCHANTMENTS
from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardType,
    Expansion,
    Tribe,
)
from deltacards.model.negative_effects import card_has_negative_effects
from deltacards.model.slots import BoardSlot
from deltacards.model.templates import CardTemplate

if TYPE_CHECKING:
    from deltacards.actions.standard import ActionContext
    from deltacards.model.entity import Entity


@dataclass(frozen=True, slots=True, eq=False)
class IsTypePredicate(Predicate):
    expected_type: CardType

    def test(self, entity: Card | CardTemplate, ctx: 'ActionContext', **kwargs) -> bool:
        return card_type_of(entity, default=None) == self.expected_type

    def __repr__(self) -> str:
        return "IS_MONSTER" if self.expected_type == CardType.MONSTER else "IS_SPELL"


@dataclass(frozen=True, slots=True, eq=False)
class DamagedPredicate(Predicate):
    def test(self, entity: 'Entity', ctx: 'ActionContext', **kwargs) -> bool:
        if card_type_of(entity, default=None) is not CardType.MONSTER:
            return False

        return entity.hp < entity.max_hp

    def __repr__(self) -> str:
        return "DAMAGED"


@dataclass(frozen=True, slots=True, eq=False)
class HasNegativeEffectsPredicate(Predicate):
    def test(self, entity: 'Entity', ctx: 'ActionContext', **kwargs) -> bool:
        buffs = attr_of(entity, 'buffs', default=None)
        keywords = attr_of(entity, 'keywords', default=None)
        statuses = attr_of(entity, 'statuses', default=None)

        if (buffs is None) or (keywords is None) or (statuses is None):
            return False

        return card_has_negative_effects(
            cost_buff=buffs.cost,
            attack_buff=buffs.attack,
            max_hp_buff=buffs.max_hp,
            keywords=keywords,
            statuses=statuses,
        )

    def __repr__(self) -> str:
        return "HAS_NEGATIVE_EFFECTS"


@dataclass(frozen=True, slots=True, eq=False)
class DeadPredicate(Predicate):
    def test(self, entity: 'Entity', ctx: 'ActionContext', **kwargs) -> bool:
        if card_type_of(entity, default=None) is not CardType.MONSTER:
            return False

        return any(
            result.monster_id == entity.id
            for result in ctx.game.log_by_type[MonsterKilledResult]
        )

    def __repr__(self) -> str:
        return "DEAD"


@dataclass(frozen=True, slots=True, eq=False)
class HasKeywordPredicate(Predicate):
    keyword: CardKeyword

    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        return has_keyword(entity, self.keyword, default=False)

    def __repr__(self) -> str:
        return f"HAS_KEYWORD({self.keyword.name})"


@dataclass(frozen=True, slots=True, eq=False)
class HasStatusPredicate(Predicate):
    status_id: CardStatusId

    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        return status_of(entity, self.status_id, default=0) > 0

    def __repr__(self) -> str:
        return f"HAS_STATUS({self.status_id.name})"


@dataclass(frozen=True, slots=True, eq=False)
class HasAbilityPredicate(Predicate):
    ability: Ability

    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        return has_ability(entity, self.ability, default=False)

    def __repr__(self) -> str:
        return f"HAS_ABILITY(Ability.{self.ability.name})"


@dataclass(frozen=True, slots=True, eq=False)
class HasTribePredicate(Predicate):
    tribe: Tribe

    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        return has_tribe(entity, self.tribe, default=False)

    def __repr__(self) -> str:
        return f"HAS_TRIBE(Tribe.{self.tribe.name})"


@dataclass(frozen=True, slots=True, eq=False)
class HasAnyTribePredicate(Predicate):
    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        return len(tribes_of(entity, default=())) > 0

    def __repr__(self) -> str:
        return f"HAS_ANY_TRIBE"


@dataclass(frozen=True, slots=True, eq=False)
class ExpansionPredicate(Predicate):
    expansion: Expansion

    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        return expansion_of(entity, default=None) == self.expansion

    def __repr__(self) -> str:
        return f"EXPANSION(Expansion.{self.expansion.name})"


@dataclass(frozen=True, slots=True, eq=False)
class GeneratedPredicate(Predicate):
    generated: bool = True

    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        is_generated = generated_of(entity, default=False)
        return is_generated if self.generated else (not is_generated)

    def __repr__(self) -> str:
        return "GENERATED" if self.generated else "NON_GENERATED"


@dataclass(frozen=True, slots=True, eq=False)
class GeneratedByPredicate(Predicate):
    creator: 'Entity | CardTemplate | TargetSelector'

    def test(self, entity: Card, ctx: 'ActionContext', **kwargs) -> bool:
        is_generated = generated_of(entity, default=False)
        if not is_generated:
            return False

        creator = self.creator
        if isinstance(creator, TargetSelector):
            creator = creator.eval_optional_one(ctx=ctx, **kwargs)
            if creator is None:
                return False

        creator_base_identity = attr_of(entity, 'creator_base_identity', default=None)
        return creator_base_identity == creator.base_identity

    def __repr__(self) -> str:
        return f"GENERATED_BY({self.creator!r})"


@dataclass(frozen=True, slots=True, eq=False)
class EmptyBoardSlotPredicate(Predicate):
    empty: bool

    def test(self, entity: BoardSlot, ctx: 'ActionContext', **kwargs) -> bool:
        if not isinstance(entity, BoardSlot):
            return False

        return (entity.monster_id is None) is self.empty

    def __repr__(self) -> str:
        return "EMPTY_SLOT" if self.empty else "OCCUPIED_SLOT"


@dataclass(frozen=True, slots=True, eq=False)
class EnchantedBoardSlotPredicate(Predicate):
    enchanted: bool

    def test(self, entity: BoardSlot, ctx: 'ActionContext', **kwargs) -> bool:
        if not isinstance(entity, BoardSlot):
            return False

        has_enchantment = ctx.game.enchantment_on_slot(entity) is not None
        return has_enchantment is self.enchanted

    def __repr__(self) -> str:
        return "ENCHANTED_SLOT" if self.enchanted else "UNENCHANTED_SLOT"


@dataclass(frozen=True, slots=True, eq=False)
class SlotHasEnchantmentPredicate(Predicate):
    name: str

    def test(self, entity: BoardSlot, ctx: 'ActionContext', **kwargs) -> bool:
        if not isinstance(entity, BoardSlot):
            return False

        enchantment = ctx.game.enchantment_on_slot(entity)
        if enchantment is None:
            return False

        return type(enchantment) is ENCHANTMENTS[self.name]

    def __repr__(self) -> str:
        return f"SLOT_HAS_ENCHANTMENT({self.name})"


@dataclass(frozen=True, slots=True, eq=False)
class IsCustomContentPredicate(Predicate):
    def test(self, entity: 'Entity', ctx: 'ActionContext', **kwargs) -> bool:
        return is_custom_content(entity.base_identity[0], entity.id)

    def __repr__(self) -> str:
        return f"IS_CUSTOM_CONTENT"


IS_MONSTER = IsTypePredicate(CardType.MONSTER)
IS_SPELL = IsTypePredicate(CardType.SPELL)

DAMAGED = DamagedPredicate()
DEAD = DeadPredicate()
HAS_NEGATIVE_EFFECTS = HasNegativeEffectsPredicate()

HAS_KEYWORD = lambda keyword: HasKeywordPredicate(keyword)
HAS_STATUS = lambda status_id: HasStatusPredicate(status_id)
HAS_ABILITY = lambda ability: HasAbilityPredicate(ability)
HAS_TRIBE = lambda tribe: HasTribePredicate(tribe)

HAS_ANY_TRIBE = HasAnyTribePredicate()

EXPANSION = lambda expansion: ExpansionPredicate(expansion)

GENERATED = GeneratedPredicate(True)
NON_GENERATED = GeneratedPredicate(False)

GENERATED_BY = lambda creator: GeneratedByPredicate(creator)

TOKEN = (RARITY == CardRarity.TOKEN)
NON_TOKEN = (RARITY < CardRarity.TOKEN)

DT = (RARITY == CardRarity.DETERMINATION)
NON_DT = (RARITY != CardRarity.DETERMINATION)

EMPTY_SLOT = EmptyBoardSlotPredicate(True)
OCCUPIED_SLOT = EmptyBoardSlotPredicate(False)

ENCHANTED_SLOT = EnchantedBoardSlotPredicate(True)
UNENCHANTED_SLOT = EnchantedBoardSlotPredicate(False)

SLOT_HAS_ENCHANTMENT = lambda name: SlotHasEnchantmentPredicate(name)

IS_CUSTOM_CONTENT = IsCustomContentPredicate()
