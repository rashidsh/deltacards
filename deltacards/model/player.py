from typing import Sequence, TYPE_CHECKING

from deltacards.engine.constants import GOLD_GAINS
from deltacards.model.containers import Board, CardContainer, Deck
from deltacards.model.entity import Entity
from deltacards.model.enums import PlayerId, Tribe
from deltacards.model.slots import BoardSlot
from deltacards.model.snapshots import PlayerSnapshot

if TYPE_CHECKING:
    from deltacards.engine.game import Game
    from deltacards.model.artifacts import Artifact
    from deltacards.model.souls import Soul


class Player(Entity):
    def __init__(
        self,
        player_id: PlayerId,
        deck: Sequence[int],
        soul_id: str,
        artifact_ids: Sequence[int],
    ):
        super().__init__(player_id)

        self.id: PlayerId = player_id

        self.starting_deck_card_ids = deck
        self.starting_soul_id = soul_id
        self.starting_artifact_ids = artifact_ids
        self.is_first_turn: bool = None

        self.soul: 'Soul' = None
        self.artifacts: list['Artifact'] = None

        self.board = Board()
        self.board_slots: list['BoardSlot'] = []
        self.hand = CardContainer()
        self.deck: Deck = None
        self.dustpile = CardContainer()
        self.erased = CardContainer()

        self.turn = 0
        self.gold = 0
        self.hp = 30
        self.max_hp = 30
        self.fatigue_counter = 0

        self.tribes_played_this_turn: set[Tribe] = set()
        self.turns_to_skip: int = 0

        self.game: 'Game' = None
        self.opponent: 'Player' = None

        self.next_lost_soul: int | None = None

    def __str__(self):
        return f"Player {self.id}"

    @property
    def controller_id(self) -> PlayerId:
        return self.id

    def gold_gain(self, turn: int) -> int:
        try:
            return GOLD_GAINS[int(not self.is_first_turn)][turn - 1]
        except IndexError:
            return 10

    def increase_gold(self, turn: int) -> None:
        self.gold += self.gold_gain(turn)

    def heal(self, amount: int) -> int:
        old_hp = self.hp
        self.hp = min(self.hp + max(amount, 0), self.max_hp)

        return self.hp - old_hp

    def set_hp(self, hp: int) -> None:
        self.hp = max(hp, 0)
        if self.hp > self.max_hp:
            self.max_hp = hp

    def set_max_hp(self, hp: int) -> None:
        self.max_hp = max(hp, 0)
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def buff(self, hp: int = 0) -> None:
        self.max_hp = max(self.max_hp + hp, 0)

        if hp >= 0:
            self.hp = max(self.hp + hp, 0)
        else:
            self.hp = min(self.hp, self.max_hp)

    def get_snapshot_attrs(self) -> dict:
        return dict(
            id=self.id,
            gold=self.gold,
            hp=self.hp,
            max_hp=self.max_hp,
        )

    def to_snapshot(self) -> 'PlayerSnapshot':
        return PlayerSnapshot(**self.get_snapshot_attrs())
