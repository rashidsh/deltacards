import asyncio
import base64
import binascii
import json
import secrets
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from deltacards.ai import AIGameController
from deltacards.ai.simple import SimpleAI
from deltacards.content.catalog import ContentCatalog
from deltacards.engine.constants import BEGINNER_DECKS
from deltacards.engine.game import Game
from deltacards.engine.runner import GameRunner, StepListener
from deltacards.model.artifacts import ArtifactRarity
from deltacards.model.enums import CardRarity
from deltacards.model.enums import PlayerId
from deltacards.model.player import Player
from deltacards.model.templates import SpellTemplate

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

    padded = text + '=' * (-len(text) % 4)

    try:
        return json.loads(base64.urlsafe_b64decode(padded).decode('utf-8'))
    except (UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("Invalid deck code") from exc


def _deck_id_list(value, name: str) -> tuple[int, ...]:
    if type(value) is not list:
        raise ValueError(f"{name} must be an array")

    if any(type(item) is not int for item in value):
        raise ValueError(f"{name} must contain integer IDs")

    return tuple(value)


def validate_deck_for_catalog(deck: dict, content: ContentCatalog) -> dict:
    if type(deck) is not dict:
        raise ValueError("Deck must be an object")

    soul_id = deck.get('soul')
    if type(soul_id) is not str or soul_id not in content.souls:
        raise ValueError("Deck uses an unknown Soul")

    card_ids = _deck_id_list(deck.get('cardIds'), 'cardIds')
    if len(card_ids) != 25:
        raise ValueError("Deck must contain exactly 25 cards")

    for card_id in card_ids:
        try:
            template = content.cards.get(card_id)
        except KeyError as exc:
            raise ValueError(f"Deck uses unknown card ID {card_id}") from exc

        if template.rarity is CardRarity.TOKEN:
            raise ValueError("Token cards cannot be placed in a deck")

        if (
            isinstance(template, SpellTemplate)
            and template.soul_id != soul_id
        ):
            raise ValueError(f"Spell {card_id} does not belong to Soul {soul_id}")

    artifact_ids = _deck_id_list(deck.get('artifactIds'), 'artifactIds')

    if len(set(artifact_ids)) != len(artifact_ids):
        raise ValueError("A deck cannot contain duplicate Artifacts")

    artifact_types = []
    for artifact_id in artifact_ids:
        try:
            artifact_type = content.artifacts[artifact_id]
        except KeyError as exc:
            raise ValueError(f"Deck uses unknown Artifact ID {artifact_id}") from exc

        if artifact_type.rarity is ArtifactRarity.TOKEN:
            raise ValueError("Token Artifacts cannot be placed in a deck")

        artifact_types.append(artifact_type)

    legendary_count = sum(
        artifact_type.rarity is ArtifactRarity.LEGENDARY
        for artifact_type in artifact_types
    )
    artifacts_valid = (
        (len(artifact_types) == 1 and legendary_count == 1)
        or (len(artifact_types) == 2 and legendary_count == 0)
    )
    if not artifacts_valid:
        raise ValueError(
            "A deck requires one Legendary Artifact or two non-Legendary Artifacts"
        )

    return {
        'soul': soul_id,
        'cardIds': card_ids,
        'artifactIds': artifact_ids,
    }


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
        seat_tokens: dict[str, PlayerId] | None = None,
    ):
        self.game_id = game_id
        self.game = game
        self.runner = runner
        self.controller = controller
        self.human_player_ids = human_player_ids
        self.bot_player_ids = bot_player_ids
        self.usernames = usernames
        self.config = config
        self.seat_tokens = dict(seat_tokens or {})

        self.expired = False
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
        content: ContentCatalog,
        human_deck_spec: str | None = None,
        bot_deck_spec: str | None = None,
    ) -> 'HostedGame':
        bot_player_id = human_player_id.opponent()
        seed = config.game_seed_base + game_id

        human_deck = cls._select_deck(
            name_or_code=(
                human_deck_spec
                if human_deck_spec is not None
                else config.human_deck_name
            ),
            game_id=game_id,
            seed=seed,
            offset=0,
        )
        bot_deck = cls._select_deck(
            name_or_code=(
                bot_deck_spec
                if bot_deck_spec is not None
                else config.bot_deck_name
            ),
            game_id=game_id,
            seed=seed,
            offset=1,
        )
        human_deck = validate_deck_for_catalog(human_deck, content)
        bot_deck = validate_deck_for_catalog(bot_deck, content)

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

        game = Game(players, content=content, seed=seed)
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

    async def expire(self) -> None:
        async with self.lock:
            self.expired = True
            sessions = tuple(self.sessions.values())
            self.sessions.clear()

        if sessions:
            await asyncio.gather(
                *(
                    session.close_expired()
                    for session in sessions
                ),
                return_exceptions=True,
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

    def player_for_token(
        self,
        token: str,
    ) -> PlayerId | None:
        return self.seat_tokens.get(token)

    def advance(
        self,
        *,
        step_listener: StepListener | None = None,
    ):
        scripted = self.game.content.runtime_limits is not None

        return self.controller.resolve_until_blocked(
            step_listener=step_listener,
            step_limit=(
                self.config.max_resolution_steps_per_command
                if scripted
                else None
            ),
            terminate_on_step_limit=scripted,
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
    def __init__(
        self,
        config: ServerConfig,
        content: ContentCatalog,
    ):
        self.config = config
        self.content = content
        self._games: dict[int, HostedGame] = {}
        self._lock = asyncio.Lock()
        self._expiration_tasks: dict[int, asyncio.Task[None]] = {}

    async def _expire_custom_game(
        self,
        game_id: int,
        hosted: HostedGame,
    ) -> None:
        try:
            await asyncio.sleep(self.config.scripted_match_lifetime_seconds)
        except asyncio.CancelledError:
            return

        async with self._lock:
            self._expiration_tasks.pop(game_id, None)

            if self._games.get(game_id) is not hosted:
                return

            del self._games[game_id]
            hosted.expired = True

        await hosted.expire()

    async def close(self) -> None:
        async with self._lock:
            tasks = tuple(self._expiration_tasks.values())
            games = tuple(self._games.values())

            self._expiration_tasks.clear()
            self._games.clear()

            for hosted in games:
                hosted.expired = True

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if games:
            await asyncio.gather(
                *(hosted.expire() for hosted in games),
                return_exceptions=True,
            )

    async def get_or_create(
        self,
        *,
        game_id: int,
        player_id: PlayerId,
        human_deck_spec: str | None = None,
        bot_deck_spec: str | None = None,
    ) -> HostedGame:
        async with self._lock:
            hosted = self._games.get(game_id)

            if hosted is None:
                hosted = HostedGame.create(
                    game_id=game_id,
                    human_player_id=player_id,
                    config=self.config,
                    content=self.content,
                    human_deck_spec=human_deck_spec,
                    bot_deck_spec=bot_deck_spec,
                )
                self._games[game_id] = hosted
                return hosted

            if hosted.seat_tokens:
                raise PlayerUnavailableError(
                    f"Game {game_id} requires a match player token"
                )

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

    async def create_custom_game(
        self,
        *,
        content: ContentCatalog,
        human_deck_spec: str,
    ) -> tuple[HostedGame, str]:
        async with self._lock:
            while True:
                game_id = secrets.randbelow(2 ** 31 - 1) + 1
                if game_id not in self._games:
                    break

            token = secrets.token_urlsafe(32)
            hosted = HostedGame.create(
                game_id=game_id,
                human_player_id=PlayerId.P1,
                config=self.config,
                content=content,
                human_deck_spec=human_deck_spec,
            )
            hosted.seat_tokens[token] = PlayerId.P1
            self._games[game_id] = hosted
            self._expiration_tasks[game_id] = asyncio.create_task(
                self._expire_custom_game(game_id, hosted)
            )

            return hosted, token

    async def get_by_token(
        self,
        game_id: int,
        token: str,
    ) -> tuple[HostedGame, PlayerId] | None:
        async with self._lock:
            hosted = self._games.get(game_id)
            if hosted is None:
                return None

            player_id = hosted.player_for_token(token)
            if player_id is None:
                return None

            return hosted, player_id

    def get(self, game_id: int) -> HostedGame | None:
        return self._games.get(game_id)

    def all_games(self) -> tuple[HostedGame, ...]:
        return tuple(self._games.values())
