import argparse
import asyncio
import logging
import re
import signal
from dataclasses import replace
from http import HTTPStatus
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

from deltacards.content.frontend import FrontendContentCatalog
from deltacards.content.loader import SOURCE_CARDS_JSON, load
from deltacards.content.registry import CONTENT
from deltacards.model.enums import PlayerId

from .config import ServerConfig
from .errors import FatalProtocolError, PlayerUnavailableError
from .games import GameRegistry
from .serializers import json_text
from .session import WebSocketSession, fatal_error_event


def http_response(
    *,
    status: HTTPStatus = HTTPStatus.OK,
    content_type: str,
    body: bytes,
) -> Response:
    return Response(
        status_code=status.value,
        reason_phrase=status.phrase,
        headers=Headers([
            ('Content-Type', content_type),
            ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-cache'),
            ('Access-Control-Allow-Origin', '*'),
        ]),
        body=body,
    )


def json_response(data: dict | list) -> Response:
    return http_response(
        content_type='application/json; charset=utf-8',
        body=json_text(data).encode('utf-8'),
    )


def deck_error_response(translation_key: str) -> dict:
    return {
        'status': 'error',
        'message': json_text({
            'args': json_text([translation_key]),
        }),
    }


class IgnoreOptionsException(logging.Filter):
    # TODO: should switch to another http / websockets library
    #  rather than continuing using `websockets` for everything and relying on hacks like this one
    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage() != "opening handshake failed":
            return True

        if record.exc_info is None:
            return True

        exc = record.exc_info[1]
        while exc is not None:
            if ("unsupported HTTP method" in str(exc)) and ("got OPTIONS" in str(exc)):
                return False

            exc = exc.__cause__ or exc.__context__

        return True


class WebSocketApplication:
    def __init__(
        self,
        config: ServerConfig | None = None,
    ):
        self.config = config or ServerConfig()
        self.registry = GameRegistry(self.config)
        self.frontend_content = FrontendContentCatalog.build(SOURCE_CARDS_JSON)

    @staticmethod
    def _parse_endpoint(
        connection: ServerConnection,
    ) -> tuple[int, PlayerId]:
        parsed = urlsplit(connection.request.path)
        path_match = re.fullmatch(r'^/game/([1-9][0-9]*)$', parsed.path)
        if path_match is None:
            raise FatalProtocolError(
                f"Invalid game endpoint {parsed.path!r}"
            )

        query = parse_qs(parsed.query, keep_blank_values=True)

        player_values = query['player_id']
        if player_values[0] not in ('1', '2'):
            raise FatalProtocolError("player_id must be 1 or 2")

        game_id = int(path_match.group(1))
        player_id = PlayerId(int(player_values[0]))

        return game_id, player_id

    async def handler(
        self,
        connection: ServerConnection,
    ) -> None:
        try:
            game_id, player_id = self._parse_endpoint(connection)
            hosted = await self.registry.get_or_create(
                game_id=game_id,
                player_id=player_id,
            )

        except PlayerUnavailableError:
            await self._fail_connection(
                connection,
                'game-error-player-unavailable',
            )
            return

        except FatalProtocolError as exc:
            await self._fail_connection(
                connection,
                exc.translation_key,
                *exc.translation_args,
            )
            return

        except Exception:
            await self._fail_connection(
                connection,
                'game-error-internal',
            )
            raise

        session = WebSocketSession(
            websocket=connection,
            hosted=hosted,
            player_id=player_id,
        )
        await session.run()

    @staticmethod
    async def _fail_connection(
        connection: ServerConnection,
        translation_key: str,
        *translation_args: object,
    ) -> None:
        try:
            await connection.send(
                json_text(
                    fatal_error_event(
                        translation_key,
                        *translation_args,
                    ),
                )
            )
        except ConnectionClosed:
            return

        try:
            await connection.close(
                code=1008,
                reason="Connection rejected",
            )
        except ConnectionClosed:
            pass

    def deck_config_action_response(
        self,
        query: dict[str, list[str]],
    ) -> dict:
        action_values = query.get('action')
        soul_values = query.get('soul')

        if not action_values or not soul_values:
            return deck_error_response('decks-error-invalid-request')

        action = action_values[0]
        soul = soul_values[0]

        if action in ('addCard', 'removeCard'):
            try:
                card_id = int(query['idCard'][0])
            except (KeyError, IndexError, ValueError):
                return deck_error_response('decks-error-card-not-owned')

            card = self.frontend_content.custom_card(card_id)
            if card is None:
                return deck_error_response('decks-error-card-not-owned')

            response_card = dict(card)
            response_card['shiny'] = query.get('isShiny', ['false'])[0].lower() == 'true'

            return {
                'soul': soul,
                'card': json_text(response_card),
            }

        if action == 'addArtifact':
            try:
                artifact_id = int(query['idArtifact'][0])
            except (KeyError, IndexError, ValueError):
                return deck_error_response('decks-error-artifact-not-owned')

            artifact = self.frontend_content.custom_artifact(artifact_id)
            if artifact is None:
                return deck_error_response('decks-error-artifact-not-owned')

            return {
                'action': 'getArtifactAdded',
                'soul': soul,
                'artifact': json_text(artifact),
            }

        return deck_error_response('decks-error-invalid-request')

    async def process_request(self, connection, request):
        parsed = urlsplit(request.path)

        if parsed.path == '/check/':
            return json_response({'status': 'ok'})

        if (
            parsed.path == '/cards-version/'
            and parse_qs(parsed.query).get('type') == ['cards']
        ):
            return json_response({
                'cardsVersion': self.frontend_content.cards_version,
                'customContent': self.frontend_content.custom_content_view(),
            })

        if parsed.path == '/cards/':
            return json_response({
                'cards': json_text(self.frontend_content.cards),
            })

        if parsed.path == '/translations/':
            locale = parse_qs(parsed.query).get('locale', ['en'])[0]
            return json_response(CONTENT.localization_entries(locale))

        if parsed.path == '/decks-config/':
            return json_response(
                self.deck_config_action_response(
                    parse_qs(parsed.query, keep_blank_values=True)
                )
            )

        asset = CONTENT.asset_at_url(parsed.path)
        if asset is not None:
            return http_response(
                content_type=asset.content_type,
                body=asset.data,
            )

        if request.headers.get('Upgrade', '').lower() != 'websocket':
            return http_response(
                status=HTTPStatus.NOT_FOUND,
                content_type='text/plain; charset=utf-8',
                body=b"Not found\n",
            )

        return None


async def run_server(
    config: ServerConfig | None = None,
) -> None:
    config = config or ServerConfig()
    load()

    application = WebSocketApplication(config)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except (NotImplementedError, RuntimeError):
            pass

    print(f"Starting WebSocket server on ws://{config.host}:{config.port}")

    ws_logger = logging.getLogger('deltacards.websockets')
    ws_logger.addFilter(IgnoreOptionsException())

    async with serve(
        application.handler,
        config.host,
        config.port,
        max_size=config.max_message_size,
        process_request=application.process_request,
        logger=ws_logger,
    ):
        await stop_event.wait()


def parse_args() -> argparse.Namespace:
    defaults = ServerConfig()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--host',
        default=defaults.host,
    )
    parser.add_argument(
        '--port',
        type=int,
        default=defaults.port,
    )
    parser.add_argument('--human-deck')
    parser.add_argument('--bot-deck')
    parser.add_argument(
        '--seed-base',
        type=int,
        default=defaults.game_seed_base,
        help=(
            'Base seed used to derive deterministic per-game seeds. '
            'The game ID is added to this value.'
        ),
    )
    parser.add_argument('--no-animations', action='store_true')
    parser.add_argument('--no-wait-times', action='store_true')
    return parser.parse_args()


def config_from_args(
    args: argparse.Namespace,
) -> ServerConfig:
    config = ServerConfig()
    presentation = replace(
        config.presentation,
        emit_animation_events=not args.no_animations,
        wait_times_enabled=not args.no_wait_times,
    )

    return replace(
        config,
        host=args.host or config.host,
        port=args.port if args.port is not None else config.port,
        presentation=presentation,
        human_deck_name=(
            args.human_deck
            if args.human_deck is not None
            else config.human_deck_name
        ),
        bot_deck_name=(
            args.bot_deck
            if args.bot_deck is not None
            else config.bot_deck_name
        ),
        game_seed_base=args.seed_base,
    )


def main() -> None:
    try:
        asyncio.run(run_server(config_from_args(parse_args())))
    except KeyboardInterrupt:
        pass
