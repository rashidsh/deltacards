from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from deltacards.actions.results import MonsterKilledResult
from deltacards.dsl.core import TargetSelector, TargetingError, ValueExpr, to_value
from deltacards.dsl.inspection import (
    _MISSING,
    attr_of,
    base_attr_of,
    template_id_of,
)
from deltacards.model.cards import Card, CardZone
from deltacards.model.enums import CardStatusId
from deltacards.model.player import Player

if TYPE_CHECKING:
    from deltacards.actions.standard import ActionContext


@dataclass(frozen=True, slots=True, eq=False)
class AttrValue(ValueExpr):
    """
    Get attribute of the candidate entity.
    Example: COST
    """
    attr: str

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        if entity is None:
            raise TargetingError(f"{self.attr.upper()} requires a candidate entity")

        value = attr_of(entity, self.attr, default=_MISSING)
        if value is _MISSING:
            raise TargetingError(f"{self.attr.upper()} attribute is not available on {type(entity).__name__}")

        return value

    def __repr__(self) -> str:
        return self.attr.upper()


@dataclass(frozen=True, slots=True, eq=False)
class TemplateIdValue(ValueExpr):
    """
    Get template id of the candidate entity.
    Example: TEMPLATE_ID
    """

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> int:
        if entity is None:
            raise TargetingError("TEMPLATE_ID requires a candidate entity")

        value = template_id_of(entity, default=_MISSING)
        if value is _MISSING:
            raise TargetingError(f"TEMPLATE_ID is not available on {type(entity).__name__}")

        return value

    def __repr__(self) -> str:
        return "TEMPLATE_ID"


@dataclass(frozen=True, slots=True, eq=False)
class BaseStatValue(ValueExpr):
    """
    Get base stat of the candidate entity.
    Example: BASE_COST
    """
    attr: str

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        if entity is None:
            raise TargetingError(f"BASE_{self.attr.upper()} requires a candidate entity")

        value = base_attr_of(entity, self.attr, default=_MISSING)
        if value is _MISSING:
            raise TargetingError(f"BASE_{self.attr.upper()} is not available on {type(entity).__name__}")

        return value

    def __repr__(self) -> str:
        return f"BASE_{self.attr.upper()}"


@dataclass(frozen=True, slots=True, eq=False)
class SelectorAttrValue(ValueExpr):
    """
    Get attribute of the entity resolved by selector.
    Example: TARGET.cost
    """
    selector: TargetSelector
    attr: str

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        target = self.selector.eval_one(ctx=ctx, **kwargs)

        if self.attr == 'controller':
            controller_id = attr_of(target, 'controller_id', default=_MISSING)
            if controller_id is _MISSING:
                raise TargetingError(f"{self.selector!r}.controller is not available on {type(target).__name__}")

            return ctx.game.player(controller_id)

        value = attr_of(target, self.attr, default=_MISSING)
        if value is _MISSING:
            raise TargetingError(f"{self.selector!r}.{self.attr} is not available on {type(target).__name__}")

        return value

    def __repr__(self) -> str:
        return f"{self.selector!r}.{self.attr}"


@dataclass(frozen=True, slots=True, eq=False)
class SelectorBaseStatValue(ValueExpr):
    """
    Get base stat of the entity resolved by selector.
    Example: TARGET.base.cost
    """
    selector: TargetSelector
    attr: str

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        target = self.selector.eval_one(ctx=ctx, **kwargs)

        value = base_attr_of(target, self.attr, default=_MISSING)
        if value is _MISSING:
            raise TargetingError(f"{self.selector!r}.base.{self.attr} is not available on {type(target).__name__}")

        return value

    def __repr__(self) -> str:
        return f"{self.selector!r}.base.{self.attr}"


@dataclass(frozen=True, slots=True, eq=False)
class SelectorBuffValue(ValueExpr):
    """
    Get stat buff value of the entity resolved by selector.
    Example: TARGET.buffs.cost
    """
    selector: TargetSelector
    attr: str

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        target = self.selector.eval_one(ctx=ctx, **kwargs)

        if not isinstance(target, Card):
            raise TargetingError(f"{self.selector!r}.buffs.{self.attr} is not available on {type(target).__name__}")

        try:
            return getattr(target.buffs, self.attr)
        except AttributeError as e:
            raise TargetingError(f"{self.selector!r}.buffs.{self.attr} is not available on {type(target).__name__}") from e

    def __repr__(self) -> str:
        return f"{self.selector!r}.buffs.{self.attr}"


@dataclass(frozen=True, slots=True, eq=False)
class SelectorDeadValue(ValueExpr):
    """
    Returns True if the selected monster has a `MonsterKilledResult` in game history.
    """
    selector: TargetSelector

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> bool:
        target = self.selector.eval_one(ctx=ctx, **kwargs)

        return any(
            result.monster_id == target.id
            for result in ctx.game.log_by_type[MonsterKilledResult]
        )

    def __repr__(self) -> str:
        return f"{self.selector!r}.dead"


@dataclass(frozen=True, slots=True, eq=False)
class SelectorStatusValue(ValueExpr):
    """
    Get status value of the entity resolved by selector.
    Example: TARGET.status(DODGE)
    """
    selector: TargetSelector
    status_id: CardStatusId

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        target = self.selector.eval_one(ctx=ctx, **kwargs)

        try:
            return target.get_status(self.status_id)
        except AttributeError as e:
            raise TargetingError(f"{self.selector!r}.status({self.status_id}) is not available on {type(target).__name__}") from e

    def __repr__(self) -> str:
        return f"{self.selector!r}.status({self.status_id})"


@dataclass(frozen=True, slots=True, eq=False)
class ClampValue(ValueExpr):
    value: ValueExpr
    lower: ValueExpr
    upper: ValueExpr

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        value = self.value.eval(ctx=ctx, entity=entity, **kwargs)
        lower = self.lower.eval(ctx=ctx, entity=entity, **kwargs)
        upper = self.upper.eval(ctx=ctx, entity=entity, **kwargs)

        assert lower <= upper
        return max(lower, min(value, upper))

    def __repr__(self) -> str:
        return f"CLAMP({self.value!r}, {self.lower!r}, {self.upper!r})"


def CLAMP(value: Any, lower: Any, upper: Any) -> ClampValue:
    return ClampValue(to_value(value), to_value(lower), to_value(upper))


@dataclass(frozen=True, slots=True, eq=False)
class LeastGreatestValue(ValueExpr):
    mode: Literal['least', 'greatest']
    a: ValueExpr
    b: ValueExpr

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        a = self.a.eval(ctx=ctx, entity=entity, **kwargs)
        b = self.b.eval(ctx=ctx, entity=entity, **kwargs)

        if self.mode == 'least':
            return a if a <= b else b
        else:
            return a if a >= b else b

    def __repr__(self) -> str:
        name = "LEAST" if self.mode == 'least' else "GREATEST"
        return f"{name}({self.a!r}, {self.b!r})"


def LEAST(a: Any, b: Any) -> LeastGreatestValue:
    return LeastGreatestValue('least', to_value(a), to_value(b))


def GREATEST(a: Any, b: Any) -> LeastGreatestValue:
    return LeastGreatestValue('greatest', to_value(a), to_value(b))


@dataclass(frozen=True, slots=True, eq=False)
class EmptySlotsValue(ValueExpr):
    selector: TargetSelector

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> int:
        from deltacards.dsl.selectors import ZoneSelector

        if not isinstance(self.selector, ZoneSelector):
            raise TargetingError(f"EMPTY_SLOTS expects a ZoneSelector, got {self.selector!r}")

        used = len(self.selector.eval(ctx=ctx, **kwargs))

        player = self.selector.player.eval_one(ctx=ctx, **kwargs)
        if self.selector.zone is CardZone.BOARD:
            cap = int(player.board.MAX_CARDS)
        elif self.selector.zone is CardZone.HAND:
            cap = 7
        else:
            raise TargetingError(f"EMPTY_SLOTS only supports HAND/BOARD, got {self.selector.zone}")

        return max(cap - used, 0)

    def __repr__(self) -> str:
        return f"EMPTY_SLOTS({self.selector!r})"


def EMPTY_SLOTS(selector: TargetSelector) -> EmptySlotsValue:
    return EmptySlotsValue(selector=selector)


@dataclass(frozen=True, slots=True, eq=False)
class SynergyTriggeredValue(ValueExpr):
    """
    Can only be used inside MAGIC trigger of a monster.
    Returns True if SYNERGY was triggered.
    """
    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> bool:
        return ctx.env.get('synergy_triggered', False)

    def __repr__(self) -> str:
        return "SYNERGY_TRIGGERED"


@dataclass(frozen=True, slots=True, eq=False)
class HasArtifactValue(ValueExpr):
    artifact_name: str

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> bool:
        if entity is None:
            raise TargetingError(f"HAS_ARTIFACT requires a candidate entity")

        if not isinstance(entity, Player):
            raise TargetingError(f"HAS_ARTIFACT is not available on {type(entity).__name__}")

        definition = ctx.game.content.artifact_by_name(self.artifact_name)
        if definition is None:
            return False

        return any(type(artifact) is definition for artifact in entity.artifacts)

    def __repr__(self) -> str:
        return "HAS_ARTIFACT"


ID = AttrValue('id')

TEMPLATE_ID = TemplateIdValue()

COST = AttrValue('cost')
RARITY = AttrValue('rarity')

ATTACK = AttrValue('attack')
HP = AttrValue('hp')
CREATOR_ID = AttrValue('creator_id')

BASE_COST = BaseStatValue('cost')
BASE_ATTACK = BaseStatValue('attack')
BASE_HP = BaseStatValue('hp')

SYNERGY_TRIGGERED = SynergyTriggeredValue()

HAS_ARTIFACT = HasArtifactValue
