import inspect
import types
import typing
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generator, Generic, Sequence, TYPE_CHECKING, TypeVar

from deltacards.actions.results import ActionResult
from deltacards.model.entity import Entity
from deltacards.model.enums import PlayerId
from deltacards.model.requests import PendingRequest

if TYPE_CHECKING:
    from deltacards.dsl.vars import Var
    from deltacards.engine.effects import EffectBase
    from deltacards.engine.game import Game


T = TypeVar('T')
_MISSING = object()


@dataclass(slots=True)
class ActionContext:
    game: 'Game'
    source: Entity | None = None
    vars: dict[str, Any] = field(default_factory=dict)
    env: dict[str, Any] = field(default_factory=dict)
    cache: dict[Any, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionCall:
    action: Any
    source: Entity
    kwargs: dict[str, Any] = field(default_factory=dict)
    env: dict[str, Any] = field(default_factory=dict)
    vars: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionOutcome:
    success: bool
    results: Sequence[ActionResult] = ()
    affected: list[Entity] | None = field(default_factory=list)
    action_calls: list[ActionCall] | None = field(default_factory=list)
    pending_request: PendingRequest | None = None

    # Optional frozen result projection for action-log and UI presentation.
    # `None` means presentation consumers should use `results`; an empty
    # sequence intentionally suppresses presentation of ordinary results.
    # Presentation results are never recorded in `game.log` or dispatched.
    presentation_results: Sequence[ActionResult] | None = None


class Arg(Generic[T]):
    def __init__(
        self,
        *,
        default: Any = _MISSING,
        many: bool = False,
        raw: bool = False,
        preserve_list: bool = False,
    ):
        self.default = default
        self.many = many
        self.raw = raw
        self.preserve_list = preserve_list

        self.name: str | None = None
        self.expected_type: Any | None = None

    def __set_name__(self, owner, name: str) -> None:
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self

        return instance._exprs.get(self.name, self.default)

    def __set__(self, instance, value) -> None:
        raise AttributeError("Action args cannot be modified at runtime")


def evaluate_expr(expr: Any, *, ctx: ActionContext, **context) -> Any:
    if hasattr(expr, 'test'):
        return expr.test(entity=context.get('entity'), ctx=ctx, **context)

    if hasattr(expr, 'eval'):
        return expr.eval(ctx=ctx, **context)

    if inspect.isclass(expr):
        return expr()

    if callable(expr):
        return expr(ctx=ctx, **context)

    return expr


@contextmanager
def bind_ctx_var(ctx: ActionContext, name: str, value: Any) -> Generator:
    """
    Temporarily bind `ctx.vars[name] = value`, restoring previous value on exit.
    Safe for nested loops.
    """
    old = ctx.vars.get(name, _MISSING)
    ctx.vars[name] = value

    try:
        yield
    finally:
        if old is _MISSING:
            ctx.vars.pop(name, None)
        else:
            ctx.vars[name] = old


class Action:
    many_arg_names: tuple[str, ...] = ()
    primary_result_type: ClassVar[type[ActionResult] | None] = None

    _arg_defs = {}

    def __init__(self, **kwargs):
        self._exprs: dict[str, Any] = {}
        self._exprs.update(kwargs)

        # Validate required args were provided
        for name, arg_def in self._arg_defs.items():
            if name not in self._exprs and arg_def.default is _MISSING:
                raise TypeError(f"Missing required argument: {name!r}")

    def __init_subclass__(cls) -> None:
        # Collect Arg definitions
        arg_defs = {}
        for base in reversed(cls.__mro__):
            for name, value in getattr(base, '__dict__', {}).items():
                if isinstance(value, Arg) and name not in arg_defs:
                    arg_defs[name] = value

        cls._arg_defs = arg_defs

        # Resolve annotations
        try:
            hints = typing.get_type_hints(cls, include_extras=True)
        except (NameError, TypeError):
            hints = getattr(cls, '__annotations__', {})

        many_arg_names: list[str] = []
        for name, arg_def in cls._arg_defs.items():
            hint = hints.get(name)
            if hint is None:
                continue

            if typing.get_origin(hint) is Arg:
                (inner,) = typing.get_args(hint) or (Any,)
                arg_def.expected_type = inner

            if arg_def.many:
                many_arg_names.append(name)

        cls.many_arg_names = tuple(many_arg_names)

    def __mul__(self, count: Any) -> 'EffectBase':
        if isinstance(count, int) and count < 0:
            raise ValueError(f"Repeat count must be >= 0, got {count}")

        from deltacards.engine.effects import For
        return For(count=count, effect=self)

    def __rshift__(self, other: Any) -> 'EffectBase':
        from deltacards.engine.effects import Seq, effectify
        return Seq(effectify(self), effectify(other))

    def __rrshift__(self, other: Any) -> 'EffectBase':
        from deltacards.engine.effects import Seq, effectify
        return Seq(effectify(other), effectify(self))

    def __repr__(self):
        kwargs_str = ', '.join(f"{key}={value!r}" for key, value in self._exprs.items())
        return f"{self.__class__.__name__}({kwargs_str})"

    def to(self, to: Any, else_: Any | None = None) -> 'EffectBase':
        from deltacards.engine.effects import Then, effectify
        return Then(effectify(self), effectify(to), effectify(else_) if else_ is not None else None)

    def store_result(self, var: 'Var') -> 'EffectBase':
        from deltacards.dsl.vars import Var
        from deltacards.engine.effects import StoreResult

        if not isinstance(var, Var):
            raise TypeError(f"Action.store_result() expects Var, got {type(var).__name__}")

        return StoreResult(self, var)

    def resolve(self, ctx: ActionContext, **kwargs) -> dict[str, Any]:
        """
        Resolve declared action args to concrete values for execute().

        If the engine already computed a value, it can pass it in `kwargs`
        under the same arg name (e.g. kwargs['target'] = <Player object>)
        and it will be used as-is.
        """
        from deltacards.dsl.core import NoTargetsError

        results: dict[str, Any] = {}
        for name, arg_def in self._arg_defs.items():
            if name in kwargs:
                value = kwargs[name]
            else:
                expr = self._exprs.get(name, arg_def.default)
                if expr is _MISSING:
                    raise TypeError(f"Required arg {name} was not set")

                if arg_def.raw:
                    results[name] = expr
                    continue

                value = evaluate_expr(expr, ctx=ctx, **kwargs)

            # If it's an Arg with many=True, the engine must already have expanded it.
            if arg_def.many and isinstance(value, (list, tuple)):
                raise TypeError(f"{self!r}: arg {name} with many=True resolved to non-sequence type: {value!r}")

            def expects_list(type_: Any) -> bool:
                if type_ is None:
                    return False

                origin = typing.get_origin(type_)

                if origin is list:
                    return True

                if origin in (typing.Union, types.UnionType):
                    return any(expects_list(arg) for arg in typing.get_args(type_))

                return False

            def expects_entity(type_: Any) -> bool:
                if type_ is None:
                    return False

                if typing.get_origin(type_) in (typing.Union, types.UnionType):
                    return any(expects_entity(arg) for arg in typing.get_args(type_))

                try:
                    return inspect.isclass(type_) and issubclass(type_, Entity)
                except TypeError:
                    return False

            arg_expects_list = expects_list(arg_def.expected_type)

            if (
                (not arg_def.many)
                and isinstance(value, list)
                and (not arg_expects_list)
                and (not arg_def.preserve_list)
            ):
                if len(value) == 0:
                    # If it's an optional arg with a default, use default; else fizzle.
                    if arg_def.default is not _MISSING:
                        value = arg_def.default
                    else:
                        raise NoTargetsError(f"{self!r}: arg {name} resolved to no targets")

                elif len(value) == 1:
                    value = value[0]

                else:
                    raise TypeError(f"{self!r}: arg {name} resolved to multiple targets: {value!r}")

            # Convert Entity ID to Entity
            if ((type(value) is int) or isinstance(value, PlayerId)) and expects_entity(arg_def.expected_type):
                if isinstance(value, (list, tuple)):  # TODO
                    raise NotImplementedError

                value = ctx.game.entity(value)

            results[name] = value

        return results

    def execute(self, *args, **kwargs) -> ActionOutcome:
        raise NotImplementedError
