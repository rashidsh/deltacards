import argparse
import json
import random
import re
from contextlib import asynccontextmanager
from dataclasses import replace

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import QueryParams
from starlette.responses import Response

from deltacards.content.catalog import ContentCatalog
from deltacards.content.loader import load
from deltacards.model.enums import PlayerId
from deltacards.scripted import (
    ScriptedContentValidationError,
    build_scripted_catalog,
    validate_scripted_pack,
)

from .config import ServerConfig
from .connection import GameSocket, SocketClosed, StarletteGameSocket
from .errors import FatalProtocolError, PlayerUnavailableError
from .games import GameRegistry
from .serializers import json_text
from .session import WebSocketSession, fatal_error_event
from ...engine.constants import BEGINNER_DECKS


def json_response(
    data: dict | list,
    *,
    status_code: int = 200,
) -> Response:
    return Response(
        content=json_text(data),
        media_type='application/json',
        status_code=status_code,
        headers={
            'Cache-Control': 'no-cache',
            'X-Content-Type-Options': 'nosniff',
        },
    )


def deck_error_response(translation_key: str) -> dict:
    return {
        'status': 'error',
        'message': json_text({
            'args': json_text([translation_key]),
        }),
    }


def api_error(
    code: str,
    message: str,
    *,
    diagnostics: list[dict] | None = None,
) -> dict:
    result = {
        'error': {
            'code': code,
            'message': message,
        },
    }

    if diagnostics is not None:
        result['diagnostics'] = diagnostics

    return result


async def decode_json_request(
    request: Request,
    *,
    maximum_size: int,
) -> tuple[object | None, Response | None]:
    media_type = request.headers.get('content-type', '').partition(';')[0].strip().lower()
    if media_type != 'application/json':
        return None, json_response(
            api_error(
                'UNSUPPORTED_MEDIA_TYPE',
                'The request must use Content-Type: application/json.',
            ),
            status_code=415,
        )

    body = bytearray()

    async for chunk in request.stream():
        if len(body) + len(chunk) > maximum_size:
            return None, json_response(
                api_error(
                    'REQUEST_TOO_LARGE',
                    'The JSON request exceeds the configured size limit.',
                ),
                status_code=413,
            )

        body.extend(chunk)

    try:
        return json.loads(body), None
    except (RecursionError, UnicodeDecodeError, json.JSONDecodeError):
        return None, json_response(
            api_error('INVALID_JSON', 'The request body must contain valid JSON.'),
            status_code=400,
        )


def get_random_beginner_deck():
    deck_name = random.choice(tuple(BEGINNER_DECKS.keys()))
    return BEGINNER_DECKS[deck_name]


class WebSocketApplication:
    def __init__(
        self,
        catalog: ContentCatalog,
        config: ServerConfig | None = None,
    ):
        self.catalog = catalog
        self.config = config or ServerConfig()
        self.registry = GameRegistry(self.config, catalog)
        self.frontend_content = catalog.frontend

    def translation_entries(
        self,
        catalog: ContentCatalog,
        locale: str,
    ) -> dict[str, str]:
        return catalog.presentation.localization_entries(locale)

    def websocket_origin_allowed(
        self,
        origin: str | None,
    ) -> bool:
        return (
            (not self.config.public_server)
            or (origin in self.config.allowed_origins)
        )

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

        except (KeyError, TypeError, ValueError):
            await self._fail_connection(
                socket,
                'game-error-invalid-command',
                'deck',
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

    async def scripted_handler(
        self,
        socket: GameSocket,
        *,
        game_id_text: str,
        player_token: str | None,
    ) -> None:
        if re.fullmatch(r'[1-9][0-9]*', game_id_text) is None:
            await self._fail_connection(
                socket,
                'game-error-invalid-command',
                'game endpoint',
            )
            return

        if not player_token:
            await self._fail_connection(
                socket,
                'game-error-player-unavailable',
            )
            return

        seat = await self.registry.get_by_token(
            int(game_id_text),
            player_token,
        )
        if seat is None:
            await self._fail_connection(
                socket,
                'game-error-player-unavailable',
            )
            return

        hosted, player_id = seat
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
            response_card['shiny'] = query.get('isShiny', 'false').lower() == 'true'

            return {
                'soul': soul,
                'card': json_text(response_card),
            }

        if action == 'addArtifact':
            try:
                artifact_id = int(query['idArtifact'])
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


def bearer_token(request: Request) -> str | None:
    authorization = request.headers.get('authorization')
    if authorization is None:
        return None

    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].casefold() != 'bearer':
        return None

    return parts[1] or None


def create_app(config: ServerConfig | None = None) -> FastAPI:
    catalog = load()
    application = WebSocketApplication(catalog, config)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            await application.registry.close()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(application.config.allowed_origins),
        allow_methods=['GET', 'POST'],
        allow_headers=['Authorization', 'Content-Type'],
        allow_credentials=False,
    )

    @app.get('/check/')
    async def check() -> Response:
        return json_response({'status': 'ok'})

    @app.post('/v1/content/validate')
    async def validate_content(request: Request) -> Response:
        pack, error = await decode_json_request(
            request,
            maximum_size=application.config.max_content_request_size,
        )
        if error is not None:
            return error

        if type(pack) is not dict:
            return json_response(
                api_error('INVALID_PACK', "A scripted content pack must be a JSON object."),
                status_code=400,
            )

        validation = validate_scripted_pack(
            pack,
            base=application.catalog,
        )
        result = validation.to_dict()

        if validation.valid:
            build = build_scripted_catalog(pack, base=application.catalog)
            base_translations = application.catalog.presentation.localization_entries('en')
            preview_translations = build.catalog.presentation.localization_entries('en')

            result['catalogPreview'] = {
                'baseCardsVersion': application.frontend_content.cards_version,
                'cardsVersion': build.catalog.frontend.cards_version,
                'customContent': build.catalog.frontend.custom_content_view(),
                'translations': {
                    key: value
                    for key, value in preview_translations.items()
                    if base_translations.get(key) != value
                },
            }

        return json_response(result)

    @app.post('/v1/games')
    async def create_scripted_game(request: Request) -> Response:
        payload, error = await decode_json_request(
            request,
            maximum_size=application.config.max_content_request_size,
        )
        if error is not None:
            return error

        if type(payload) is not dict:
            return json_response(
                api_error(
                    'INVALID_REQUEST',
                    'The game creation request must be a JSON object.',
                ),
                status_code=400,
            )

        pack = payload.get('pack')
        deck = payload.get('deck')

        if (
            type(pack) is not dict
            or type(deck) is not str
        ):
            return json_response(
                api_error(
                    'INVALID_REQUEST',
                    'The request requires a pack object and a string deck code.',
                ),
                status_code=400,
            )

        try:
            build = build_scripted_catalog(
                pack,
                base=application.catalog,
            )
        except ScriptedContentValidationError as exc:
            return json_response(
                api_error(
                    'INVALID_CONTENT',
                    'The scripted content pack is invalid.',
                    diagnostics=[
                        diagnostic.to_dict()
                        for diagnostic in exc.diagnostics
                    ],
                ),
                status_code=422,
            )
        except (TypeError, ValueError) as exc:
            return json_response(
                api_error('INVALID_CONTENT', str(exc)),
                status_code=422,
            )

        try:
            hosted, token = await application.registry.create_custom_game(
                content=build.catalog,
                human_deck_spec=deck.strip() or json.dumps(get_random_beginner_deck()),
            )
        except (KeyError, TypeError, ValueError):
            return json_response(
                api_error(
                    'INVALID_DECK',
                    'The configured deck code is invalid for this catalog.',
                ),
                status_code=422,
            )

        return json_response({
            'gameId': hosted.game_id,
            'playerToken': token,
            'assignedIds': build.assigned_ids,
        }, status_code=201)

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
        return json_response(
            application.translation_entries(application.catalog, locale)
        )

    @app.get('/decks-config/')
    async def decks_config(request: Request) -> Response:
        return json_response(
            application.deck_config_action_response(request.query_params)
        )

    async def authorized_game(
        request: Request,
        game_id: int,
    ):
        player_token = bearer_token(request)
        if not player_token:
            return None

        seat = await application.registry.get_by_token(game_id, player_token)
        if seat is None:
            return None

        return seat[0]

    @app.get('/v1/games/{game_id}/cards-version')
    async def game_cards_version(
        game_id: int,
        request: Request,
    ) -> Response:
        hosted = await authorized_game(request, game_id)
        if hosted is None:
            return Response(status_code=404)

        frontend = hosted.game.content.frontend
        return json_response({
            'cardsVersion': frontend.cards_version,
            'customContent': frontend.custom_content_view(),
        })

    @app.get('/v1/games/{game_id}/cards')
    async def game_cards(
        game_id: int,
        request: Request,
    ) -> Response:
        hosted = await authorized_game(request, game_id)
        if hosted is None:
            return Response(status_code=404)

        return json_response({
            'cards': json_text(hosted.game.content.frontend.cards),
        })

    @app.get('/v1/games/{game_id}/translations')
    async def game_translations(
        game_id: int,
        request: Request,
        locale: str = 'en',
    ) -> Response:
        hosted = await authorized_game(request, game_id)
        if hosted is None:
            return Response(status_code=404)

        return json_response(
            application.translation_entries(
                hosted.game.content,
                locale or 'en'
            )
        )

    if not application.config.public_server:
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

    @app.websocket('/v1/games/{game_id}/ws')
    async def scripted_game_socket(
        websocket: WebSocket,
        game_id: str,
        player_token: str | None = None,
    ) -> None:
        if not application.websocket_origin_allowed(websocket.headers.get('origin')):
            await websocket.close(
                code=1008,
                reason="Origin is not allowed",
            )
            return

        await websocket.accept()
        socket = StarletteGameSocket(websocket)
        await application.scripted_handler(
            socket,
            game_id_text=game_id,
            player_token=player_token,
        )

    @app.get('/{asset_path:path}')
    async def content_asset(asset_path: str) -> Response:
        asset = application.catalog.presentation.asset_at_url(f'/{asset_path}')
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
    parser.add_argument(
        '--public',
        dest='public_server',
        action='store_true',
        help='Expose only token-scoped scripted games.',
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
        public_server=args.public_server,
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
