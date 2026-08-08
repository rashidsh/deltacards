from typing import ClassVar, TYPE_CHECKING

from deltacards.model.entity import Entity
from deltacards.model.enums import Ability, PlayerId
from deltacards.model.snapshots import EnchantmentSnapshot
from deltacards.model.types import BaseIdentity

if TYPE_CHECKING:
    from deltacards.actions.base import ActionContext
    from deltacards.model.player import Player

ENCHANTMENTS: dict[str, type['Enchantment']] = {}


def enchantment(enchantment_id: str):
    def wrapper(class_: type['Enchantment']):
        if enchantment_id in ENCHANTMENTS:
            raise ValueError(f"Enchantment with ID {enchantment_id} already exists")

        class_.definition_id = enchantment_id
        ENCHANTMENTS[enchantment_id] = class_
        return class_

    return wrapper


class Enchantment(Entity):
    __slots__ = 'owner_id', 'controller_id', 'slot_id', 'counter', 'active', 'creator_id', 'creator_base_identity'

    definition_id: ClassVar[str]
    name: ClassVar[str]
    initial_counter: ClassVar[int] = 0

    def __init__(
        self,
        id: int,
        controller_id: PlayerId,
        slot_id: int,
        creator_id: int | None = None,
        creator_base_identity: BaseIdentity | None = None,
    ):
        super().__init__(id)

        self.owner_id = controller_id
        self.controller_id = controller_id
        self.slot_id = slot_id

        self.counter = self.initial_counter
        self.active = True

        self.creator_id = creator_id
        self.creator_base_identity = creator_base_identity

    def __str__(self) -> str:
        return self.name

    def _get_controller(self, ctx: 'ActionContext') -> 'Player':
        return ctx.game.player(self.controller_id)

    @property
    def base_identity(self) -> BaseIdentity:
        return 'enchantment', self.definition_id

    @property
    def is_generated(self) -> bool:
        return self.creator_id is not None

    def get_ability(self, ability: Ability):
        if not self.active:
            return None

        return super().get_ability(ability)

    def has_ability(self, ability: Ability) -> bool:
        if not self.active:
            return False

        return super().has_ability(ability)

    def to_snapshot(self) -> EnchantmentSnapshot:
        return EnchantmentSnapshot(
            id=self.id,
            definition_id=self.definition_id,
            name=self.name,
            controller_id=self.controller_id,
            slot_id=self.slot_id,
            counter=self.counter,
            active=self.active,
            creator_id=self.creator_id,
            creator_base_identity=self.creator_base_identity,
        )
