import asyncio
import base64
import binascii
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from deltacards.ai import AIGameController
from deltacards.ai.simple import SimpleAI
from deltacards.engine.constants import BEGINNER_DECKS
from deltacards.engine.game import Game
from deltacards.engine.runner import GameRunner, StepListener
from deltacards.model.enums import PlayerId
from deltacards.model.player import Player

from .adapter import FrontendAdapter
from .config import (
    DEFAULT_BOT_USERNAME,
    DEFAULT_HUMAN_USERNAME,
    ServerConfig,
)
from .errors import PlayerUnavailableError

if TYPE_CHECKING:
    from .session import WebSocketSession


def deck_from_code(text: str) -> dict:
    text = text.strip()

    if not text:
        raise ValueError("Empty deck code")

    if text.startswith('{'):
        return json.loads(text)

    try:
        return json.loads(base64.urlsafe_b64decode(text).decode('utf-8'))
    except (UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("Invalid deck code") from exc


@dataclass(slots=True)
class PendingPlay:
    request_id: int
    card_id: int
    board_pos: int | None


class HostedGame:
    def __init__(
        self,
        *,
        game_id: int,
        game: Game,
        runner: GameRunner,
        controller: AIGameController,
        human_player_ids: set[PlayerId],
        bot_player_ids: set[PlayerId],
        usernames: dict[PlayerId, str],
        config: ServerConfig,
    ):
        self.game_id = game_id
        self.game = game
        self.runner = runner
        self.controller = controller
        self.human_player_ids = human_player_ids
        self.bot_player_ids = bot_player_ids
        self.usernames = usernames
        self.config = config

        self.lock = asyncio.Lock()
        self.sessions: dict[PlayerId, 'WebSocketSession'] = {}

        self.pending_play: PendingPlay | None = None

        self.battle_logs: dict[PlayerId, list[dict]] = defaultdict(list)

        self.adapter = FrontendAdapter(
            game_id=game_id,
            runner=runner,
            config=config,
            usernames=usernames,
        )

    @staticmethod
    def _select_deck(
        *,
        name_or_code: str | None,
        game_id: int,
        seed: int,
        offset: int,
    ) -> dict:
        if name_or_code is not None:
            normalized_name = name_or_code.lower()
            if normalized_name in BEGINNER_DECKS:
                return BEGINNER_DECKS[normalized_name]

            try:
                return deck_from_code(name_or_code)
            except ValueError:
                raise ValueError("Invalid deck")

        names = tuple(BEGINNER_DECKS)
        index = (game_id * 2 + seed + offset) % len(names)

        return BEGINNER_DECKS[names[index]]

    @classmethod
    def create(
        cls,
        *,
        game_id: int,
        human_player_id: PlayerId,
        config: ServerConfig,
    ) -> 'HostedGame':
        bot_player_id = human_player_id.opponent()

        if config.game_seed_base is None:
            game_seed_base = random.randint(0, int(2e9))
        else:
            game_seed_base = config.game_seed_base

        seed = game_seed_base + game_id

        human_deck = cls._select_deck(
            name_or_code=config.human_deck_name,
            game_id=game_id,
            seed=seed,
            offset=0,
        )
        bot_deck = cls._select_deck(
            name_or_code=config.bot_deck_name,
            game_id=game_id,
            seed=seed,
            offset=1,
        )

        deck_by_player = {
            human_player_id: human_deck,
            bot_player_id: bot_deck,
        }

        players = tuple(
            Player(
                player_id,
                deck=tuple(deck_by_player[player_id]['cardIds']),
                soul_id=deck_by_player[player_id]['soul'],
                artifact_ids=tuple(
                    deck_by_player[player_id]['artifactIds']
                ),
            )
            for player_id in (PlayerId.P1, PlayerId.P2)
        )

        game = Game(players, seed=seed)
        runner = GameRunner(game)

        controller = AIGameController(
            runner=runner,
            agents={
                bot_player_id: SimpleAI(),
            },
        )

        usernames = {
            human_player_id: f"{DEFAULT_HUMAN_USERNAME} {human_player_id.value}",
            bot_player_id: DEFAULT_BOT_USERNAME,
        }

        return cls(
            game_id=game_id,
            game=game,
            runner=runner,
            controller=controller,
            human_player_ids={human_player_id},
            bot_player_ids={bot_player_id},
            usernames=usernames,
            config=config,
        )

    def replace_session(
        self,
        player_id: PlayerId,
        session: 'WebSocketSession',
    ) -> 'WebSocketSession | None':
        previous = self.sessions.get(player_id)
        self.sessions[player_id] = session
        return previous

    def remove_session(
        self,
        player_id: PlayerId,
        session: 'WebSocketSession',
    ) -> None:
        if self.sessions.get(player_id) is session:
            del self.sessions[player_id]

    def is_current_session(
        self,
        player_id: PlayerId,
        session: 'WebSocketSession',
    ) -> bool:
        return self.sessions.get(player_id) is session

    def pending_for(self, player_id: PlayerId):
        matching = [
            request
            for request in self.game.pending_requests.values()
            if request.player_id is player_id
        ]

        if len(matching) == 0:
            return None

        if len(matching) > 1:
            raise RuntimeError(
                f"Player {player_id.value} has multiple pending "
                f"requests: {[r.request_id for r in matching]!r}"
            )

        return matching[0]

    def advance(
        self,
        *,
        step_listener: StepListener | None = None,
    ):
        return self.controller.resolve_until_blocked(
            step_listener=step_listener,
        )

    def append_battle_logs(
        self,
        viewer_id: PlayerId,
        battle_logs,
    ) -> None:
        logs = self.battle_logs[viewer_id]

        for battle_log in battle_logs:
            logs.insert(0, battle_log)

        del logs[self.config.battle_log_limit:]


class GameRegistry:
    def __init__(self, config: ServerConfig):
        self.config = config
        self._games: dict[int, HostedGame] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        *,
        game_id: int,
        player_id: PlayerId,
    ) -> HostedGame:
        async with self._lock:
            hosted = self._games.get(game_id)

            if hosted is None:
                hosted = HostedGame.create(
                    game_id=game_id,
                    human_player_id=player_id,
                    config=self.config,
                )
                self._games[game_id] = hosted
                return hosted

            if player_id in hosted.bot_player_ids:
                raise PlayerUnavailableError(
                    f"Player {player_id.value} in game "
                    f"{game_id} is controlled by a bot"
                )

            if player_id not in hosted.human_player_ids:
                raise PlayerUnavailableError(
                    f"Player {player_id.value} is not a human "
                    f"seat in game {game_id}"
                )

            return hosted

    def get(self, game_id: int) -> HostedGame | None:
        return self._games.get(game_id)

    def all_games(self) -> tuple[HostedGame, ...]:
        return tuple(self._games.values())
