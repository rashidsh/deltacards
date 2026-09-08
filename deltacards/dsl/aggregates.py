from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from deltacards.dsl.core import TargetSelector, TargetingError, ValueExpr, to_value
from deltacards.dsl.inspection import tribes_of
from deltacards.model.enums import Tribe

if TYPE_CHECKING:
    from deltacards.actions.standard import ActionContext


def _append_unique(result: list[Any], seen_hashable: set[Any], value: Any) -> None:
    try:
        # Hashable value: use the set for fast lookup.
        if value in seen_hashable:
            return

    except TypeError:
        # Unhashable value: must fall back to linear scan.
        if any(value == existing for existing in result):
            return

        result.append(value)
        return

    seen_hashable.add(value)
    result.append(value)


@dataclass(frozen=True, slots=True, eq=False)
class ExistsValue(ValueExpr):
    selector: TargetSelector

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> bool:
        return bool(self.selector.eval(ctx=ctx, **kwargs))

    def __repr__(self) -> str:
        return f"EXISTS({self.selector!r})"


def EXISTS(selector: TargetSelector) -> ExistsValue:
    return ExistsValue(selector=selector)


@dataclass(frozen=True, slots=True, eq=False)
class CountValue(ValueExpr):
    selector: TargetSelector

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> int:
        return len(self.selector.eval(ctx=ctx, **kwargs))

    def __repr__(self) -> str:
        return f"COUNT({self.selector!r})"


def COUNT(selector: TargetSelector) -> CountValue:
    return CountValue(selector)


@dataclass(frozen=True, slots=True, eq=False)
class SumValue(ValueExpr):
    selector: TargetSelector
    value: ValueExpr
    default: ValueExpr

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> int:
        items = self.selector.eval(ctx=ctx, **kwargs)
        if not items:
            return self.default.eval(ctx=ctx, entity=entity, **kwargs)

        total = 0
        for item in items:
            total += self.value.eval(ctx=ctx, entity=item, **kwargs)

        return total

    def __repr__(self) -> str:
        return f"SUM({self.selector!r}, {self.value!r})"


def SUM(selector: TargetSelector, value: Any, default: int = 0) -> SumValue:
    return SumValue(
        selector=selector,
        value=to_value(value),
        default=to_value(default),
    )


@dataclass(frozen=True, slots=True, eq=False)
class MinMaxValue(ValueExpr):
    mode: str
    selector: TargetSelector
    value: ValueExpr
    default: ValueExpr | None = None

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        items = self.selector.eval(ctx=ctx, **kwargs)
        if not items:
            if self.default is None:
                raise TargetingError(f"{self.mode.upper()}VAL({self.selector!r}) got no items")

            return self.default.eval(ctx=ctx, entity=entity, **kwargs)

        values = [
            self.value.eval(ctx=ctx, entity=item, **kwargs)
            for item in items
        ]

        return min(values) if self.mode == 'min' else max(values)

    def __repr__(self) -> str:
        name = "MINVAL" if self.mode == 'min' else "MAXVAL"
        return f"{name}({self.selector!r}, {self.value!r})"


def MINVAL(selector: TargetSelector, value: Any, default: Any = None) -> MinMaxValue:
    return MinMaxValue(
        mode='min',
        selector=selector,
        value=to_value(value),
        default=None if default is None else to_value(default),
    )


def MAXVAL(selector: TargetSelector, value: Any, default: Any = None) -> MinMaxValue:
    return MinMaxValue(
        mode='max',
        selector=selector,
        value=to_value(value),
        default=None if default is None else to_value(default),
    )


@dataclass(frozen=True, slots=True, eq=False)
class UniqueValuesValue(ValueExpr):
    selector: TargetSelector
    key: ValueExpr

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> list[Any]:
        result = []
        seen_hashable = set()

        for item in self.selector.eval(ctx=ctx, **kwargs):
            value = self.key.eval(ctx=ctx, entity=item, **kwargs)
            _append_unique(result, seen_hashable, value)

        return result

    def __repr__(self) -> str:
        return f"UNIQUE_VALUES({self.selector!r}, {self.key!r})"


def UNIQUE_VALUES(selector: TargetSelector, key: Any) -> UniqueValuesValue:
    return UniqueValuesValue(selector=selector, key=to_value(key))


@dataclass(frozen=True, slots=True, eq=False)
class CountDistinctValue(ValueExpr):
    selector: TargetSelector
    key: ValueExpr

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> int:
        result = []
        seen_hashable = set()

        for item in self.selector.eval(ctx=ctx, **kwargs):
            value = self.key.eval(ctx=ctx, entity=item, **kwargs)
            _append_unique(result, seen_hashable, value)

        return len(result)

    def __repr__(self) -> str:
        return f"COUNT_DISTINCT({self.selector!r}, {self.key!r})"


def COUNT_DISTINCT(selector: TargetSelector, key: Any | None = None) -> CountDistinctValue:
    from deltacards.dsl.values import TEMPLATE_ID

    return CountDistinctValue(
        selector=selector,
        key=TEMPLATE_ID if key is None else to_value(key),
    )


@dataclass(frozen=True, slots=True, eq=False)
class UniqueTribesValue(ValueExpr):
    selector: TargetSelector

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> list[Tribe]:
        result: list[Tribe] = []
        seen_hashable: set[Any] = set()

        for item in self.selector.eval(ctx=ctx, **kwargs):
            tribes = tribes_of(item, default=())
            for tribe in tribes:
                _append_unique(result, seen_hashable, tribe)

        return result

    def __repr__(self) -> str:
        return f"UNIQUE_TRIBES({self.selector!r})"


def UNIQUE_TRIBES(selector: TargetSelector) -> UniqueTribesValue:
    return UniqueTribesValue(selector=selector)


@dataclass(frozen=True, slots=True, eq=False)
class CountUniqueTribesValue(ValueExpr):
    selector: TargetSelector

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> int:
        return len(
            UNIQUE_TRIBES(self.selector)
            .eval(ctx=ctx, entity=entity, **kwargs)
        )

    def __repr__(self) -> str:
        return f"COUNT_UNIQUE_TRIBES({self.selector!r})"


def COUNT_UNIQUE_TRIBES(selector: TargetSelector) -> CountUniqueTribesValue:
    return CountUniqueTribesValue(selector=selector)
