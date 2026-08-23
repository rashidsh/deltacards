from abc import ABC, ABCMeta
from typing import Any, Iterable, TYPE_CHECKING

from deltacards.actions.methods import ActionProxy
from deltacards.engine.modifiers import IntModifier
from deltacards.model.enums import Ability
from deltacards.model.types import BaseIdentity

if TYPE_CHECKING:
    from deltacards.actions.results import ActionResult
    from deltacards.engine.game import Game


_MISSING_EVENT_EFFECT = object()


class EventHandler:
    __slots__ = 'result_type', 'effect', 'condition', 'function'

    def __init__(
        self,
        result_type: type['ActionResult'],
        *,
        effect: Any = _MISSING_EVENT_EFFECT,
        condition: Any = True,
        function: Any | None = None,
    ):
        self.result_type = result_type
        self.effect = effect
        self.condition = condition
        self.function = function

    def __call__(self, function):
        if self.effect is not _MISSING_EVENT_EFFECT:
            raise TypeError("`on_event()` with `effect` provided cannot be used to decorate a function")

        if not callable(function):
            raise TypeError("`on_event()` decorator `effect` must be callable")

        return EventHandler(
            self.result_type,
            condition=self.condition,
            function=function,
        )

    def __set_name__(self, owner, name):
        if (self.function is None) and (self.effect is _MISSING_EVENT_EFFECT):
            raise TypeError("`on_event()` used as a class attribute requires an effect")

        owner.post_event_handlers.setdefault(self.result_type, []).append(self)

        if self.function is not None:
            setattr(owner, name, self.function)


class EntityMeta(ABCMeta):
    def __new__(mcls, name, bases, attrs):
        attrs['_abilities'] = {}
        attrs['var_definitions'] = {}
        attrs['post_event_handlers'] = {}

        cls = super().__new__(mcls, name, bases, attrs)

        for ability in Ability:
            effect = getattr(cls, ability.value, None)
            if effect is not None:
                cls._abilities[ability] = effect

        cls._need_condition = getattr(cls, 'need', None)

        return cls


class Entity(ABC, metaclass=EntityMeta):
    __slots__ = 'id', 'state'

    _abilities: dict[Ability, Any]
    _need_condition: Any | None

    var_definitions: dict
    post_event_handlers: dict

    def __init__(self, id: int):
        self.id = id

        self.state: dict[str, Any] = {}

    @classmethod
    def declared_ability_names(cls) -> set[str]:
        return set(ability.name for ability in cls._abilities.keys())

    @property
    def actions(self) -> ActionProxy:
        return ActionProxy(self)

    @property
    def base_identity(self) -> BaseIdentity:
        raise NotImplementedError

    def get_ability(self, ability: Ability):
        effect = self._abilities.get(ability)
        if effect is None:
            return None

        if hasattr(effect, '__get__'):
            return effect.__get__(self, type(self))

        return effect

    def has_ability(self, ability: Ability) -> bool:
        return self._abilities.get(ability) is not None

    def iter_modifiers(self, game: 'Game') -> Iterable[IntModifier]:
        return ()

    def to_snapshot(self):
        raise NotImplementedError

    def serialize(self) -> dict[str, Any]:
        raise NotImplementedError


def on_event(
    action: type['ActionResult'],
    effect: Any = _MISSING_EVENT_EFFECT,
    *,
    condition: Any = True,
) -> EventHandler:
    """Create either a callback decorator or a declarative event handler."""
    return EventHandler(
        action,
        effect=effect,
        condition=condition,
    )
