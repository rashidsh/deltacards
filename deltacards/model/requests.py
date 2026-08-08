from dataclasses import dataclass, field
from typing import Callable, TypeAlias, Union

from deltacards.model.entity import Entity
from deltacards.model.enums import PlayerId


@dataclass
class PendingRequest:
    request_id: int
    player_id: PlayerId
    request_type: str
    source_id: PlayerId | int | None = field(init=False, default=None)


@dataclass
class ChoicePrompt:
    def option_ids(self) -> set[int]:
        raise NotImplementedError


@dataclass
class ChooseEntityPrompt(ChoicePrompt):
    options: list[Entity]

    def option_ids(self) -> set[int]:
        return {c.id for c in self.options}


@dataclass(frozen=True, slots=True)
class ChoiceResponse:
    request_id: int
    player_id: PlayerId
    selected_option_ids: tuple[int, ...]


@dataclass
class PendingChoiceRequest(PendingRequest):
    request_type: str = field(init=False, default='choice')
    prompt: ChoicePrompt
    on_choose: Callable
    allow_cancel: bool = field(default=False)

    def validate(self, response: ChoiceResponse) -> tuple[bool, str]:
        if response.request_id != self.request_id:
            return False, 'invalid_request_id'
        if response.player_id != self.player_id:
            return False, 'invalid_player_id'

        if self.allow_cancel:
            if len(response.selected_option_ids) > 1:
                return False, 'wrong_selection_count'
        else:
            if len(response.selected_option_ids) != 1:
                return False, 'wrong_selection_count'

        available_option_ids = self.prompt.option_ids()
        if any((option_id not in available_option_ids) for option_id in response.selected_option_ids):
            return False, 'invalid_option_id'

        if len(set(response.selected_option_ids)) != len(response.selected_option_ids):
            return False, 'duplicate_option_ids_not_allowed'

        return True, 'ok'


@dataclass(frozen=True, slots=True)
class PlayMonster:
    card_id: int
    board_slot: int


@dataclass(frozen=True, slots=True)
class PlaySpell:
    card_id: int


@dataclass(frozen=True, slots=True)
class Attack:
    attacker_id: int
    defender_id: int


@dataclass(frozen=True, slots=True)
class EndTurn:
    pass


PlayerAction = Union[PlayMonster, PlaySpell, Attack, EndTurn]


@dataclass(frozen=True, slots=True)
class PlayerActionResponse:
    request_id: int
    player_id: PlayerId
    action: PlayerAction


@dataclass
class PendingPlayerActionRequest(PendingRequest):
    request_type: str = field(init=False, default='player_action')

    def validate(self, response: PlayerActionResponse) -> tuple[bool, str]:
        if response.player_id != self.player_id:
            return False, 'invalid_player_id'

        return True, 'ok'


@dataclass
class MulliganPrompt:
    request_id: int
    player_id: PlayerId
    offered_card_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MulliganResponse:
    request_id: int
    player_id: PlayerId
    replace_card_ids: tuple[int, ...]


@dataclass
class PendingMulliganRequest(PendingRequest):
    request_type: str = field(init=False, default='mulligan')
    prompt: MulliganPrompt

    def validate(self, response: MulliganResponse) -> tuple[bool, str]:
        if response.request_id != self.request_id:
            return False, 'invalid_request_id'
        if response.player_id != self.player_id:
            return False, 'invalid_player_id'

        if any((card_id not in self.prompt.offered_card_ids) for card_id in response.replace_card_ids):
            return False, 'invalid_card_id'

        if len(set(response.replace_card_ids)) != len(response.replace_card_ids):
            return False, 'duplicate_card_ids_not_allowed'

        return True, 'ok'


EngineInput: TypeAlias = PlayerActionResponse | ChoiceResponse | MulliganResponse
