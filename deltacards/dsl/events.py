from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from deltacards.actions.results import ActionResult
from deltacards.dsl.core import TargetSelector, TargetingError, ValueExpr, resolve_selector_value

if TYPE_CHECKING:
    from deltacards.actions.base import ActionContext


def _event_result(ctx: 'ActionContext') -> ActionResult:
    try:
        result = ctx.env['event_result']
    except KeyError as e:
        raise TargetingError("EVENT is only available in event handlers") from e

    if not isinstance(result, ActionResult):
        raise TargetingError("`ctx.env['event_result']` must contain an ActionResult")

    return result


def _resolve_event_path(ctx: 'ActionContext', path: tuple[str, ...]) -> Any:
    value = _event_result(ctx)
    for name in path:
        try:
            value = getattr(value, name)
        except AttributeError as e:
            raise TargetingError(
                f"EVENT.{'.'.join(path)} is not available on {type(value).__name__}"
            ) from e

    return value


@dataclass(frozen=True, slots=True, eq=False)
class EventValue(ValueExpr):
    path: tuple[str, ...]

    def eval(self, ctx: 'ActionContext', entity: Any | None = None, **kwargs) -> Any:
        return _resolve_event_path(ctx, self.path)

    def __getattr__(self, name: str) -> 'EventValue':
        if name.startswith('__'):
            raise AttributeError(name)

        if name == 'test':  # for evaluate_expr()
            raise AttributeError(name)

        return EventValue((*self.path, name))

    def __repr__(self) -> str:
        return f"EVENT.{'.'.join(self.path)}"


@dataclass(frozen=True, slots=True, eq=False)
class EventSelector(TargetSelector):
    path: tuple[str, ...]
    display_name: str

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        value = _resolve_event_path(ctx, self.path)
        return resolve_selector_value(value, ctx=ctx, **kwargs)

    def __repr__(self) -> str:
        return self.display_name


class EventAccessor:
    __slots__ = ()

    @property
    def subject(self) -> EventSelector:
        return EventSelector(
            path=('history_subject',),
            display_name='EVENT.subject',
        )

    def matches(self, *conditions: Any) -> TargetSelector:
        """Return the primary event subject filtered by every condition."""
        selector = self.subject
        for condition in conditions:
            selector = selector & condition

        return selector

    def select(self, field: str) -> EventSelector:
        if not field:
            raise ValueError("EVENT.select() requires a field name")

        return EventSelector(
            path=tuple(field.split('.')),
            display_name=f"EVENT.select({field!r})",
        )

    def __getattr__(self, name: str) -> EventValue:
        if name.startswith('__'):
            raise AttributeError(name)

        return EventValue((name,))

    def __repr__(self) -> str:
        return "EVENT"


EVENT = EventAccessor()
