from typing import TYPE_CHECKING

from deltacards.model.entity import Entity
from deltacards.model.enums import PlayerId
from deltacards.model.snapshots import BoardSlotSnapshot
from deltacards.model.types import BaseIdentity

if TYPE_CHECKING:
    from deltacards.actions.base import ActionContext
    from deltacards.model.player import Player


class BoardSlot(Entity):
    __slots__ = 'owner_id', 'controller_id', 'pos', 'monster_id', 'enchantment_id'

    def __init__(
        self,
        id: int,
        controller_id: PlayerId,
        pos: int,
    ):
        super().__init__(id)

        self.owner_id = controller_id
        self.controller_id = controller_id
        self.pos = pos

        self.monster_id: int | None = None
        self.enchantment_id: int | None = None

    def __str__(self) -> str:
        return f"Player {self.controller_id.value} slot {self.pos + 1}"

    def _get_controller(self, ctx: 'ActionContext') -> 'Player':
        return ctx.game.player(self.controller_id)

    @property
    def base_identity(self) -> BaseIdentity:
        return (
            'board-slot',
            f'{self.controller_id.value}:{self.pos}',
        )

    def to_snapshot(self) -> BoardSlotSnapshot:
        return BoardSlotSnapshot(
            id=self.id,
            controller_id=self.controller_id,
            pos=self.pos,
            monster_id=self.monster_id,
            enchantment_id=self.enchantment_id,
        )
