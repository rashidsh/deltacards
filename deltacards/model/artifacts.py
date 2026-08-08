from enum import Enum
from typing import ClassVar, TYPE_CHECKING

from deltacards.model.entity import Entity
from deltacards.model.enums import Ability, PlayerId
from deltacards.model.snapshots import ArtifactSnapshot
from deltacards.model.types import BaseIdentity

if TYPE_CHECKING:
    from deltacards.actions.standard import ActionContext
    from deltacards.model.player import Player

ARTIFACTS: dict[int, type['Artifact']] = {}


def artifact(artifact_id: int):
    def wrapper(class_: type['Artifact']):
        if artifact_id in ARTIFACTS:
            raise ValueError(f"Artifact with ID {artifact_id} already exists")

        class_.definition_id = artifact_id
        ARTIFACTS[artifact_id] = class_
        return class_

    return wrapper


class ArtifactRarity(Enum):
    BASE = 'base'
    COMMON = 'common'
    LEGENDARY = 'legendary'
    TOKEN = 'token'


class Artifact(Entity):
    __slots__ = 'owner_id', 'controller_id', 'counter', 'active'

    definition_id: ClassVar[int]
    name: ClassVar[str]
    rarity: ClassVar[ArtifactRarity]
    initial_counter: ClassVar[int] = 0

    def __init__(self, id: int, controller_id: PlayerId):
        super().__init__(id)

        self.owner_id = controller_id
        self.controller_id = controller_id

        self.counter = self.initial_counter
        self.active = True

    def __str__(self):
        return self.name

    def _get_controller(self, ctx: 'ActionContext') -> 'Player':
        return ctx.game.player(self.controller_id)

    @property
    def base_identity(self) -> BaseIdentity:
        return 'artifact', self.definition_id

    @property
    def is_quest(self) -> bool:
        return False

    def get_ability(self, ability: Ability):
        if not self.active:
            return None

        return super().get_ability(ability)

    def has_ability(self, ability: Ability) -> bool:
        if not self.active:
            return False

        return super().has_ability(ability)

    def to_snapshot(self) -> ArtifactSnapshot:
        return ArtifactSnapshot(
            id=self.id,
            definition_id=self.definition_id,
            name=self.name,
            controller_id=self.controller_id,
            counter=self.counter,
            active=self.active,
        )

    def toggle(self, enabled: bool):
        self.active = enabled


class QuestArtifact(Artifact):
    __slots__ = ()

    quest_goal: ClassVar[int | None] = None

    @property
    def is_quest(self) -> bool:
        return True
