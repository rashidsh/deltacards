from typing import ClassVar

from deltacards.actions.standard import *
from deltacards.model.entity import Entity
from deltacards.model.enums import PlayerId
from deltacards.model.snapshots import SoulSnapshot
from deltacards.model.types import BaseIdentity

SOULS: dict[str, type['Soul']] = {}


def soul(soul_id: str):
    def wrapper(class_: type['Soul']):
        if soul_id in SOULS:
            raise ValueError(f"Soul with ID {soul_id} already exists")

        class_.definition_id = soul_id

        if 'name' not in class_.__dict__:
            class_.name = class_.__name__.upper()

        SOULS[soul_id] = class_
        return class_

    return wrapper


class Soul(Entity):
    __slots__ = 'owner_id', 'controller_id'

    definition_id: ClassVar[str]
    name: ClassVar[str]

    def __init__(self, id: int, controller_id: PlayerId):
        super().__init__(id)

        self.owner_id = controller_id
        self.controller_id = controller_id

    def __str__(self):
        return self.name

    def _get_controller(self, ctx: ActionContext):
        return ctx.game.player(self.controller_id)

    @property
    def base_identity(self) -> BaseIdentity:
        return 'soul', self.definition_id

    def to_snapshot(self) -> SoulSnapshot:
        return SoulSnapshot(
            id=self.id,
            definition_id=self.definition_id,
            name=self.name,
            controller_id=self.controller_id,
        )
