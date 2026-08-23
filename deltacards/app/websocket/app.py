import argparse
import re
from dataclasses import replace

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import QueryParams
from starlette.responses import Response

from deltacards.content.frontend import FrontendContentCatalog
from deltacards.content.loader import SOURCE_CARDS_JSON, load
from deltacards.content.registry import CONTENT
from deltacards.model.enums import PlayerId

from .config import ServerConfig
from .connection import GameSocket, SocketClosed, StarletteGameSocket
from .errors import FatalProtocolError, PlayerUnavailableError
from .games import GameRegistry
from .serializers import json_text
from .session import WebSocketSession, fatal_error_event


def json_response(data: dict | list) -> Response:
    return Response(
        content=json_text(data),
        media_type='application/json',
        headers={'Cache-Control': 'no-cache'},
    )


def deck_error_response(translation_key: str) -> dict:
    return {
        'status': 'error',
        'message': json_text({
            'args': json_text([translation_key]),
        }),
    }


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
        game_id_text: str,
        player_id_text: str | None,
    ) -> tuple[int, PlayerId]:
        if re.fullmatch(r'[1-9][0-9]*', game_id_text) is None:
            raise FatalProtocolError(
                f"Invalid game endpoint '/game/{game_id_text}'"
            )

        if player_id_text not in ('1', '2'):
            raise FatalProtocolError("player_id must be 1 or 2")

        game_id = int(game_id_text)
        player_id = PlayerId(int(player_id_text))

        return game_id, player_id

    async def handler(
        self,
        socket: GameSocket,
        *,
        game_id_text: str,
        player_id_text: str | None,
        human_deck_text: str | None,
        bot_deck_text: str | None,
    ) -> None:
        try:
            game_id, player_id = self._parse_endpoint(game_id_text, player_id_text)
            human_deck_spec = human_deck_text or None
            bot_deck_spec = bot_deck_text or None
            hosted = await self.registry.get_or_create(
                game_id=game_id,
                player_id=player_id,
                human_deck_spec=human_deck_spec,
                bot_deck_spec=bot_deck_spec,
            )

        except PlayerUnavailableError:
            await self._fail_connection(
                socket,
                'game-error-player-unavailable',
            )
            return

        except FatalProtocolError as exc:
            await self._fail_connection(
                socket,
                exc.translation_key,
                *exc.translation_args,
            )
            return

        except Exception:
            await self._fail_connection(
                socket,
                'game-error-internal',
            )
            raise

        session = WebSocketSession(
            websocket=socket,
            hosted=hosted,
            player_id=player_id,
        )
        await session.run()

    @staticmethod
    async def _fail_connection(
        socket: GameSocket,
        translation_key: str,
        *translation_args: object,
    ) -> None:
        try:
            await socket.send_text(
                json_text(
                    fatal_error_event(
                        translation_key,
                        *translation_args,
                    ),
                )
            )
        except SocketClosed:
            return

        try:
            await socket.close(
                code=1008,
                reason="Connection rejected",
            )
        except SocketClosed:
            pass

    def deck_config_action_response(
        self,
        query: QueryParams,
    ) -> dict:
        action_values = query.getlist('action')
        soul_values = query.getlist('soul')

        if not action_values or not soul_values:
            return deck_error_response('decks-error-invalid-request')

        action = action_values[0]
        soul = soul_values[0]

        if action in ('addCard', 'removeCard'):
            try:
                card_id = int(query.getlist('idCard')[0])
            except (IndexError, ValueError):
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


def create_app(config: ServerConfig | None = None) -> FastAPI:
    load()

    application = WebSocketApplication(config)

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.get('/check/')
    async def check() -> Response:
        return json_response({'status': 'ok'})

    @app.get('/cards-version/')
    async def cards_version(request: Request) -> Response:
        if request.query_params.getlist('type') != ['cards']:
            return Response(status_code=404)

        return json_response({
            'cardsVersion': application.frontend_content.cards_version,
            'customContent': application.frontend_content.custom_content_view(),
        })

    @app.get('/cards/')
    async def cards() -> Response:
        return json_response({
            'cards': json_text(application.frontend_content.cards),
        })

    @app.get('/translations/')
    async def translations(request: Request) -> Response:
        locale_values = [
            value
            for value in request.query_params.getlist('locale')
            if value
        ]
        locale = locale_values[0] if locale_values else 'en'
        return json_response(CONTENT.localization_entries(locale))

    @app.get('/decks-config/')
    async def decks_config(request: Request) -> Response:
        return json_response(
            application.deck_config_action_response(request.query_params)
        )

    @app.websocket('/game/{game_id}')
    async def game_socket(
        websocket: WebSocket,
        game_id: str,
        player_id: str | None = None,
        human_deck: str | None = None,
        bot_deck: str | None = None,
    ) -> None:
        await websocket.accept()
        socket = StarletteGameSocket(websocket)
        await application.handler(
            socket,
            game_id_text=game_id,
            player_id_text=player_id,
            human_deck_text=human_deck,
            bot_deck_text=bot_deck,
        )

    @app.get('/{asset_path:path}')
    async def content_asset(asset_path: str) -> Response:
        asset = CONTENT.asset_at_url(f'/{asset_path}')
        if asset is None:
            return Response(status_code=404)

        return Response(
            content=asset.data,
            media_type=asset.content_type,
        )

    return app


def run_server(
    config: ServerConfig | None = None,
) -> None:
    config = config or ServerConfig()

    uvicorn.run(
        create_app(config),
        host=config.host,
        port=config.port,
        ws_max_size=config.max_message_size,
    )


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
        run_server(config_from_args(parse_args()))
    except KeyboardInterrupt:
        pass
