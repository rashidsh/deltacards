import operator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

from deltacards.actions.methods import ActionMethods
from deltacards.model.enums import CardStatusId

if TYPE_CHECKING:
    from deltacards.actions.standard import ActionContext
    from deltacards.model.entity import Entity


SYMBOLS = {
    operator.add: '+',
    operator.sub: '-',
    operator.mul: '*',
    operator.truediv: '/',
    operator.floordiv: '//',
    operator.mod: '%',

    operator.and_: '&',
    operator.or_: '|',
    operator.not_: '~',

    operator.eq: '==',
    operator.ne: '!=',
    operator.lt: '<',
    operator.le: '<=',
    operator.ge: '>=',
    operator.gt: '>',
}


# --------------------
# Exceptions
# --------------------

class TargetingError(Exception):
    """Base exception for DSL errors."""


class NoTargetsError(TargetingError):
    """Raised when a selector is expected to produce at least one target but there were no targets."""


class AmbiguousTargetError(TargetingError):
    """Raised when a selector is expected to produce exactly one target but produced more than one."""


# --------------------
# Helpers
# --------------------

def resolve_selector_value(value: Any, ctx: 'ActionContext', **kwargs) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, TargetSelector):
        return value.eval(ctx=ctx, **kwargs)

    return [value]


# --------------------
# Value expressions
# --------------------

class ValueExpr(ABC):
    __slots__ = ()

    @abstractmethod
    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        pass

    def __bool__(self) -> bool:
        raise TypeError("Cannot evaluate ValueExpr to boolean; check DSL syntax")

    # Arithmetic operations
    def __add__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.add, self, to_value(other))

    def __radd__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.add, to_value(other), self)

    def __sub__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.sub, self, to_value(other))

    def __rsub__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.sub, to_value(other), self)

    def __mul__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.mul, self, to_value(other))

    def __rmul__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.mul, to_value(other), self)

    def __truediv__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.truediv, self, to_value(other))

    def __floordiv__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.floordiv, self, to_value(other))

    def __mod__(self, other) -> 'ValueExpr':
        return BinaryValue(operator.mod, self, to_value(other))

    def __neg__(self):
        return NegValue(self)

    # Boolean operations
    def __and__(self, other: 'ValueExpr | Predicate') -> 'ValueExpr':
        if not isinstance(other, (ValueExpr, Predicate)):
            return NotImplemented

        if isinstance(other, Predicate):
            return BinaryValue(operator.and_, BooleanValue(self), PredicateAsValueExpr(other))

        return BinaryValue(operator.and_, BooleanValue(self), BooleanValue(other))

    def __rand__(self, other):
        return self.__and__(other)

    def __or__(self, other: 'ValueExpr | Predicate') -> 'ValueExpr':
        if not isinstance(other, (ValueExpr, Predicate)):
            return NotImplemented

        if isinstance(other, Predicate):
            return BinaryValue(operator.or_, BooleanValue(self), PredicateAsValueExpr(other))

        return BinaryValue(operator.or_, BooleanValue(self), BooleanValue(other))

    def __ror__(self, other):
        return self.__or__(other)

    def __invert__(self) -> 'ValueExpr':
        return NotValue(self)

    # Comparisons
    def __eq__(self, other) -> 'Predicate':
        return ComparisonPredicate(self, operator.eq, to_value(other))

    def __ne__(self, other) -> 'Predicate':
        return ComparisonPredicate(self, operator.ne, to_value(other))

    def __lt__(self, other) -> 'Predicate':
        return ComparisonPredicate(self, operator.lt, to_value(other))

    def __le__(self, other) -> 'Predicate':
        return ComparisonPredicate(self, operator.le, to_value(other))

    def __ge__(self, other) -> 'Predicate':
        return ComparisonPredicate(self, operator.ge, to_value(other))

    def __gt__(self, other) -> 'Predicate':
        return ComparisonPredicate(self, operator.gt, to_value(other))


@dataclass(frozen=True, slots=True, eq=False)
class PredicateAsValueExpr(ValueExpr):
    pred: Predicate

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        return self.pred.test(entity, ctx=ctx, **kwargs)


@dataclass(frozen=True, slots=True, eq=False)
class LiteralValue(ValueExpr):
    value: Any

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        return self.value

    def __repr__(self) -> str:
        return repr(self.value)


def to_value(x) -> ValueExpr:
    return x if isinstance(x, ValueExpr) else LiteralValue(x)


@dataclass(frozen=True, slots=True, eq=False)
class BinaryValue(ValueExpr):
    op: Callable[[Any, Any], Any]
    left: ValueExpr
    right: ValueExpr

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        return self.op(
            self.left.eval(ctx=ctx, entity=entity, **kwargs),
            self.right.eval(ctx=ctx, entity=entity, **kwargs),
        )

    def __repr__(self) -> str:
        return f"({self.left!r} {SYMBOLS[self.op]} {self.right!r})"


@dataclass(frozen=True, slots=True, eq=False)
class NegValue(ValueExpr):
    value: Any

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        return -self.value.eval(ctx=ctx, entity=entity, **kwargs)

    def __repr__(self) -> str:
        return f"(-{self.value!r})"


@dataclass(frozen=True, slots=True, eq=False)
class NotValue(ValueExpr):
    value: Any

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        return not self.value.eval(ctx=ctx, entity=entity, **kwargs)

    def __repr__(self) -> str:
        return f"(~{self.value!r})"


@dataclass(frozen=True, slots=True, eq=False)
class BooleanValue(ValueExpr):
    value: Any

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        return bool(self.value.eval(ctx=ctx, entity=entity, **kwargs))

    def __repr__(self) -> str:
        return f"bool({self.value!r})"


# --------------------
# Predicates
# --------------------

class Predicate(ABC):
    __slots__ = ()

    def __bool__(self) -> bool:
        raise TypeError("Cannot evaluate Predicate to boolean; check DSL syntax")

    def __and__(self, other: 'Predicate') -> 'Predicate':
        if not isinstance(other, Predicate):
            return NotImplemented

        return AndPredicate(self, other)

    def __or__(self, other: 'Predicate') -> 'Predicate':
        if not isinstance(other, Predicate):
            return NotImplemented

        return OrPredicate(self, other)

    def __invert__(self) -> 'Predicate':
        return NotPredicate(self)

    @abstractmethod
    def test(self, entity: 'Entity', ctx: 'ActionContext', **kwargs) -> bool:
        pass


@dataclass(frozen=True, slots=True, eq=False)
class AndPredicate(Predicate):
    left: Predicate
    right: Predicate

    def test(self, entity: Any, ctx: 'ActionContext', **kwargs) -> bool:
        return self.left.test(entity, ctx=ctx, **kwargs) and self.right.test(entity, ctx=ctx, **kwargs)

    def __repr__(self) -> str:
        return f"({self.left!r} & {self.right!r})"


@dataclass(frozen=True, slots=True, eq=False)
class OrPredicate(Predicate):
    left: Predicate
    right: Predicate

    def test(self, entity: Any, ctx: 'ActionContext', **kwargs) -> bool:
        return self.left.test(entity, ctx=ctx, **kwargs) or self.right.test(entity, ctx=ctx, **kwargs)

    def __repr__(self) -> str:
        return f"({self.left!r} | {self.right!r})"


@dataclass(frozen=True, slots=True, eq=False)
class NotPredicate(Predicate):
    pred: Predicate

    def test(self, entity: Any, ctx: 'ActionContext', **kwargs) -> bool:
        return not self.pred.test(entity, ctx=ctx, **kwargs)

    def __repr__(self) -> str:
        return f"(~{self.pred!r})"


@dataclass(frozen=True, slots=True, eq=False)
class ComparisonPredicate(Predicate):
    left: ValueExpr
    op: Callable[[Any, Any], bool]
    right: ValueExpr

    def test(self, entity: Any, ctx: 'ActionContext', **kwargs) -> bool:
        return bool(self.op(
            self.left.eval(ctx=ctx, entity=entity, **kwargs),
            self.right.eval(ctx=ctx, entity=entity, **kwargs),
        ))

    def __repr__(self) -> str:
        return f"({self.left!r} {SYMBOLS[self.op]} {self.right!r})"


# --------------------
# Transforms
# --------------------

class Transform(ABC):
    __slots__ = ()

    def __bool__(self) -> bool:
        raise TypeError("Cannot evaluate Transform to boolean; check DSL syntax")

    @abstractmethod
    def apply(self, entities: list[Any], *, ctx: 'ActionContext', **kwargs) -> list[Any]:
        pass


# --------------------
# Selectors
# --------------------

@dataclass(frozen=True, slots=True, eq=False)
class Exclude:
    """NOT operand. Used by `TargetSelector`."""
    selector: 'TargetSelector'


@dataclass(frozen=True, slots=True, eq=False)
class _BaseStatAccessor:
    selector: 'TargetSelector'

    def __getattr__(self, name: str) -> ValueExpr:
        if name in ('cost', 'attack', 'hp', 'max_hp'):
            from deltacards.dsl.values import SelectorBaseStatValue
            return SelectorBaseStatValue(self.selector, attr=name)

        raise AttributeError(name)


@dataclass(frozen=True, slots=True, eq=False)
class _BuffAccessor:
    selector: 'TargetSelector'

    def __getattr__(self, name: str) -> ValueExpr:
        if name in ('cost', 'attack', 'max_hp'):
            from deltacards.dsl.values import SelectorBuffValue
            return SelectorBuffValue(self.selector, attr=name)

        raise AttributeError(name)


class TargetSelector(ABC, ActionMethods):
    __slots__ = ()

    def __bool__(self) -> bool:
        raise TypeError("Cannot evaluate TargetSelector to boolean; check DSL syntax")

    def __and__(self, other) -> 'TargetSelector':
        if isinstance(other, TargetSelector):
            return IntersectionSelector(self, other)

        if isinstance(other, Exclude):
            return DifferenceSelector(self, other.selector)

        if isinstance(other, Predicate):
            return FilterSelector(self, other)

        if isinstance(other, ValueExpr):
            # Accept boolean `ValueExpr` objects as filters
            return FilterSelector(
                self,
                ComparisonPredicate(to_value(other), operator.eq, LiteralValue(True)),
            )

        return NotImplemented

    def __or__(self, other: 'TargetSelector') -> 'TargetSelector':
        if not isinstance(other, TargetSelector):
            return NotImplemented

        return UnionSelector(self, other)

    def __invert__(self) -> Exclude:
        return Exclude(self)

    def __rshift__(self, transform: Transform) -> 'TargetSelector':
        if not isinstance(transform, Transform):
            return NotImplemented

        return TransformedSelector(self, transform)

    def __getitem__(self, item: int | slice | ValueExpr) -> 'TargetSelector':
        return SliceSelector(self, to_value(item))

    def __getattr__(self, name: str) -> ValueExpr:
        if name in (
            'id',
            'template_id',
            'template_name',
            'rarity',
            'zone',
            'cost',
            'attack',
            'hp',
            'hp_missing',
            'max_hp',
            'age',
            'pos',
            'has_attacked',
            'controller_id',
            'controller',
            'creator_id',
            'is_generated',
            'gold',
            'turn',
            'counter',
            'quest_goal',
            'monster_id',
            'slot_id',
            'enchantment_id',
            'active',
        ):
            from deltacards.dsl.values import SelectorAttrValue
            return SelectorAttrValue(self, attr=name)

        raise AttributeError(name)

    @abstractmethod
    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        pass

    def eval_one(self, ctx: 'ActionContext', **kwargs) -> Any:
        items = self.eval(ctx=ctx, **kwargs)
        if not items:
            raise NoTargetsError(f"No targets for selector {self!r}")

        if len(items) != 1:
            raise AmbiguousTargetError(f"Expected exactly 1 target from selector {self!r}, got {len(items)}")

        return items[0]

    def eval_optional_one(self, ctx: 'ActionContext', **kwargs) -> Any | None:
        items = self.eval(ctx=ctx, **kwargs)
        if not items:
            return None

        if len(items) != 1:
            raise AmbiguousTargetError(f"Expected <=1 targets from selector {self!r}, got {len(items)}")

        return items[0]

    @property
    def base(self) -> _BaseStatAccessor:
        return _BaseStatAccessor(self)

    @property
    def buffs(self) -> _BuffAccessor:
        return _BuffAccessor(self)

    def top(self, n: int) -> 'TargetSelector':
        assert n >= 0
        return self[:n]

    def bottom(self, n: int) -> 'TargetSelector':
        assert n >= 0
        if n == 0:
            return self[:0]

        return self[-n:]

    def first(self) -> 'TargetSelector':
        return self[0]

    def last(self) -> 'TargetSelector':
        return self[-1]

    @property
    def dead(self) -> ValueExpr:
        from deltacards.dsl.values import SelectorDeadValue
        return SelectorDeadValue(self)

    def artifact(self, name: str):
        from deltacards.dsl.selectors import PlayerArtifactSelector
        return PlayerArtifactSelector(self, name=name)

    def status(self, status_id: CardStatusId):
        from deltacards.dsl.values import SelectorStatusValue
        return SelectorStatusValue(self, status_id=status_id)


@dataclass(frozen=True, slots=True, eq=False)
class UnionSelector(TargetSelector):
    left: TargetSelector
    right: TargetSelector

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        a = self.left.eval(ctx=ctx, **kwargs)
        b = self.right.eval(ctx=ctx, **kwargs)

        result = []
        seen_ids = set()

        for entity in [*a, *b]:
            if entity.id in seen_ids:
                continue

            seen_ids.add(entity.id)
            result.append(entity)

        return result

    def __repr__(self) -> str:
        return f"({self.left!r} | {self.right!r})"


@dataclass(frozen=True, slots=True, eq=False)
class IntersectionSelector(TargetSelector):
    left: TargetSelector
    right: TargetSelector

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        a = self.left.eval(ctx=ctx, **kwargs)
        b = self.right.eval(ctx=ctx, **kwargs)

        b_keys = {x.id for x in b}
        return [x for x in a if x.id in b_keys]

    def __repr__(self) -> str:
        return f"({self.left!r} & {self.right!r})"


@dataclass(frozen=True, slots=True, eq=False)
class DifferenceSelector(TargetSelector):
    left: TargetSelector
    right: TargetSelector

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        a = self.left.eval(ctx=ctx, **kwargs)
        b = self.right.eval(ctx=ctx, **kwargs)

        b_keys = {x.id for x in b}
        return [x for x in a if x.id not in b_keys]

    def __repr__(self) -> str:
        return f"({self.left!r} & ~{self.right!r})"


@dataclass(frozen=True, slots=True, eq=False)
class FilterSelector(TargetSelector):
    inner: TargetSelector
    pred: Predicate

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        items = self.inner.eval(ctx=ctx, **kwargs)
        return [x for x in items if self.pred.test(x, ctx=ctx, **kwargs)]

    def __repr__(self) -> str:
        return f"({self.inner!r} & {self.pred!r})"


@dataclass(frozen=True, slots=True, eq=False)
class TransformedSelector(TargetSelector):
    inner: TargetSelector
    transform: Transform

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        items = self.inner.eval(ctx=ctx, **kwargs)
        return self.transform.apply(items, ctx=ctx, **kwargs)

    def __repr__(self) -> str:
        return f"({self.inner!r} >> {self.transform!r})"


@dataclass(frozen=True, slots=True, eq=False)
class SliceSelector(TargetSelector):
    inner: TargetSelector
    item: ValueExpr

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        items = self.inner.eval(ctx=ctx, **kwargs)
        slice_or_index = self.item.eval(ctx=ctx, **kwargs)

        if isinstance(slice_or_index, slice):
            return items[slice_or_index]

        try:
            return [items[slice_or_index]]
        except IndexError:
            return []

    def __repr__(self) -> str:
        return f"{self.inner!r}[{self.item!r}]"
