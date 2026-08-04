import json
import re
import traceback
from typing import Any

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

from deltacards.actions.results import MonsterSummonedResult, SpellCastResult
from deltacards.actions.standard import Kill
from deltacards.engine.runner import EngineUpdate
from deltacards.model.cards import Card, Monster, Spell
from deltacards.model.enchantments import Enchantment
from deltacards.model.entity import Entity
from deltacards.model.enums import CardZone, PlayerId
from deltacards.model.player import Player
from deltacards.model.requests import (
    Attack,
    ChoiceResponse,
    ChooseEntityPrompt,
    EndTurn,
    MulliganResponse,
    PendingChoiceRequest,
    PendingMulliganRequest,
    PendingPlayerActionRequest,
    PlayMonster,
    PlaySpell,
    PlayerActionResponse,
)
from deltacards.model.slots import BoardSlot

from .errors import (
    FatalProtocolError,
    UnsupportedFrontendRequestError,
)
from .games import (
    HostedGame,
    PendingPlay,
)
from .serializers import (
    decode_wire_slot_id,
    json_text,
    wire_slot_id,
)


def fatal_error_event(
    translation_key: str,
    *translation_args: object,
) -> dict:
    return {
        'action': 'getGameError',
        'message': json_text({
            'args': json_text([
                translation_key,
                *translation_args,
            ]),
        }),
    }


def _parse_decimal_int(
    value: Any,
    *,
    field_name: str,
    allow_negative: bool = False,
) -> int:
    if type(value) is int:
        result = value

    elif isinstance(value, str):
        pattern = r'-?[0-9]+' if allow_negative else r'[0-9]+'
        if re.fullmatch(pattern, value) is None:
            raise FatalProtocolError(
                f"{field_name} must be a decimal integer"
            )
        result = int(value)

    else:
        raise FatalProtocolError(
            f"{field_name} must be an integer or decimal string"
        )

    if not allow_negative and result < 0:
        raise FatalProtocolError(
            f"{field_name} cannot be negative"
        )

    return result


def _validate_fields(
    data: dict[str, Any],
    *,
    required: set[str],
) -> None:
    missing = required - data.keys()
    if missing:
        raise FatalProtocolError(
            f"Missing protocol fields: {sorted(missing)!r}"
        )

    unknown = data.keys() - required
    if unknown:
        raise FatalProtocolError(
            f"Unknown protocol fields: {sorted(unknown)!r}"
        )


class WebSocketSession:
    def __init__(
        self,
        *,
        websocket: ServerConnection,
        hosted: HostedGame,
        player_id: PlayerId,
    ):
        self.websocket = websocket
        self.hosted = hosted
        self.player_id = player_id

        self._stopping = False

    # ---------------------
    # Connection lifecycle
    # ---------------------

    async def run(self) -> None:
        try:
            async with self.hosted.lock:
                previous = self.hosted.replace_session(self.player_id, self)

            if (previous is not None) and (previous is not self):
                await previous.close_replaced()

            async with self.hosted.lock:
                update = self.hosted.advance()
                request = self._current_request()

                waiting_card_range = (
                    self._waiting_card_range_view(request)
                    if isinstance(
                        request,
                        PendingChoiceRequest,
                    )
                    else None
                )

                await self.send_event(
                    self.hosted.adapter.connect_event(
                        viewer_id=self.player_id,
                        battle_logs=list(
                            self.hosted.battle_logs[self.player_id]
                        ),
                        waiting_card_range=waiting_card_range,
                    )
                )

                await self._emit_update(
                    update,
                    synchronize=False,
                    present_request=waiting_card_range is None,
                )

            if self._stopping:
                return

            async for message in self.websocket:
                if isinstance(message, bytes):
                    raise FatalProtocolError(
                        "Binary WebSocket frames are not supported"
                    )

                async with self.hosted.lock:
                    if not self.hosted.is_current_session(
                        self.player_id,
                        self,
                    ):
                        return

                    await self._handle_text_message(message)

                if self._stopping:
                    return

        except ConnectionClosed:
            return

        except UnsupportedFrontendRequestError as exc:
            print(f"Unsupported frontend request in game {self.hosted.game_id}: {exc}")
            await self.fail_fatally(
                'game-error-unsupported-request',
                type(exc).__name__,
            )

        except FatalProtocolError as exc:
            print(f"Fatal protocol error in game {self.hosted.game_id} for player {self.player_id.value}: {exc}")
            await self.fail_fatally(
                exc.translation_key,
                *exc.translation_args,
            )

        except Exception:
            print(f"Unhandled WebSocket session error in game {self.hosted.game_id}:\n{traceback.format_exc()}")
            await self.fail_fatally(
                'game-error-internal',
            )

        finally:
            self._stopping = True
            async with self.hosted.lock:
                self.hosted.remove_session(
                    self.player_id,
                    self,
                )

    async def _close(
        self,
        code: int,
        reason: str,
    ) -> None:
        try:
            await self.websocket.close(
                code=code,
                reason=reason,
            )
        except ConnectionClosed:
            pass

    async def close_replaced(self) -> None:
        self._stopping = True
        await self._close(
            4001,
            "Replaced by a newer connection",
        )

    async def fail_fatally(
        self,
        translation_key: str,
        *translation_args: object,
    ) -> None:
        self._stopping = True
        try:
            await self.send_event(
                fatal_error_event(
                    translation_key,
                    *translation_args,
                )
            )
        except ConnectionClosed:
            return

        await self._close(1008, "Protocol error")

    # --------------------
    # Sending events
    # --------------------

    async def send_event(self, event: dict) -> None:
        await self.websocket.send(json_text(event))

    async def send_events(
        self,
        events: list[dict],
    ) -> None:
        for event in events:
            await self.send_event(event)

    # --------------------
    # Pending requests
    # --------------------

    def _current_request(self):
        return self.hosted.pending_for(self.player_id)

    def _require_entity(self, entity_id: int):
        try:
            return self.hosted.game.entity(entity_id)
        except KeyError as exc:
            raise FatalProtocolError(
                f"Unknown runtime entity ID {entity_id}"
            ) from exc

    def _choice_wire_id(self, entity: Entity) -> int:
        if isinstance(entity, Player):
            return -entity.id.value

        if isinstance(entity, BoardSlot):
            return wire_slot_id(
                entity.controller_id,
                entity.pos,
            )

        if isinstance(entity, Enchantment):
            slot = self.hosted.game.entity(entity.slot_id)
            if not isinstance(slot, BoardSlot):
                raise UnsupportedFrontendRequestError(
                    "Enchantment is not attached to a valid "
                    "Board Slot"
                )

            return wire_slot_id(
                slot.controller_id,
                slot.pos,
            )

        if (
            isinstance(entity, Monster)
            and entity.zone is CardZone.BOARD
        ):
            return entity.id

        if isinstance(entity, Card):
            if (
                entity.zone is CardZone.HAND
                and entity.controller_id is self.player_id
            ):
                return entity.id

            raise UnsupportedFrontendRequestError(
                "A direct Card target must be visible in the "
                "connected player's Hand"
            )

        raise UnsupportedFrontendRequestError(
            f"Unsupported direct target type "
            f"{type(entity).__name__}"
        )

    def _choice_source(
        self,
        request: PendingChoiceRequest,
    ) -> tuple[Card, int | None]:
        pending_play = self.hosted.pending_play

        if (
            pending_play is not None
            and pending_play.request_id == request.request_id
        ):
            card = self.hosted.game.card(pending_play.card_id)
            return card, pending_play.board_pos

        if request.source_id is None:
            raise UnsupportedFrontendRequestError(
                "Choice request has no source Entity"
            )

        source = self.hosted.game.entity(request.source_id)
        if not isinstance(source, (Monster, Spell)):
            raise UnsupportedFrontendRequestError(
                f"Choice source {type(source).__name__} cannot be "
                f"presented by the existing frontend"
            )

        if isinstance(source, Monster):
            return source, source.pos

        return source, None

    def _build_choice_event(
        self,
        request: PendingChoiceRequest,
    ) -> tuple[dict, dict[int, int]]:
        source, board_pos = self._choice_source(request)

        if not isinstance(
            request.prompt,
            ChooseEntityPrompt,
        ):
            raise UnsupportedFrontendRequestError(
                f"Unsupported choice prompt "
                f"{type(request.prompt).__name__}"
            )

        options = request.prompt.options
        if not options:
            raise UnsupportedFrontendRequestError(
                "Choice request contains no options"
            )

        pending_play = self.hosted.pending_play
        is_initial_play = (
            pending_play is not None
            and pending_play.request_id == request.request_id
        )
        all_local_hand_cards = all(
            isinstance(option, Card)
            and option.zone is CardZone.HAND
            and option.controller_id is self.player_id
            for option in options
        )

        card_list_mode = all(
            isinstance(option, Card)
            and not (
                isinstance(option, Monster)
                and option.zone is CardZone.BOARD
            )
            for option in options
        ) and not (
            is_initial_play
            and all_local_hand_cards
        )

        wire_to_engine: dict[int, int] = {}

        if card_list_mode:
            selection_field = {
                'selectCards': json_text([
                    self.hosted.adapter.views.card_view(option)
                    for option in options
                ]),
            }

            for option in options:
                wire_to_engine[int(option.id)] = int(option.id)

        else:
            targets: list[int] = []

            for option in options:
                wire_id = self._choice_wire_id(option)

                if wire_id in wire_to_engine:
                    raise UnsupportedFrontendRequestError(
                        f"Two engine options map to frontend target "
                        f"{wire_id}"
                    )

                wire_to_engine[wire_id] = int(option.id)
                targets.append(wire_id)

            selection_field = {
                'availableTargets': json_text(targets),
            }

        if isinstance(source, Monster):
            event = {
                'action': 'getMonsterTemp',
                'monster': json_text(self.hosted.adapter.views.card_view(source)),
                'x': (
                    int(board_pos)
                    if board_pos is not None
                    else 0
                ),
                **selection_field,
            }

        elif isinstance(source, Spell):
            event = {
                'action': 'getSpellTemp',
                'spell': json_text(self.hosted.adapter.views.card_view(source)),
                **selection_field,
            }

        return event, wire_to_engine

    def _waiting_card_range_view(
        self,
        request: PendingChoiceRequest,
    ) -> dict | None:
        event, _ = self._build_choice_event(request)
        select_cards = event.get('selectCards')

        if not isinstance(select_cards, str):
            return None

        if event['action'] == 'getMonsterTemp':
            source = json.loads(event['monster'])
            source['tempX'] = int(event['x'])
        else:
            source = json.loads(event['spell'])

        source['selectCards'] = json.loads(select_cards)
        return source

    async def _present_request(self, request) -> None:
        if isinstance(request, PendingMulliganRequest):
            await self.send_event(
                self.hosted.adapter.mulligan_event(
                    request.prompt.offered_card_ids
                )
            )
            return

        if isinstance(request, PendingChoiceRequest):
            event, _ = self._build_choice_event(request)
            await self.send_event(event)
            return

        if isinstance(request, PendingPlayerActionRequest):
            return

        raise UnsupportedFrontendRequestError(
            f"Unsupported pending request "
            f"{type(request).__name__}"
        )

    def _wire_target_is_possible(self, target_id: int) -> bool:
        if target_id < 0:
            return target_id in (-PlayerId.P1, -PlayerId.P2)

        return (
            decode_wire_slot_id(target_id) is not None
            or target_id in self.hosted.game.entities
        )

    # --------------------
    # Update emission
    # --------------------

    def _advance_with_capture(self):
        capture = self.hosted.adapter.begin_update_capture(
            self.player_id
        )
        update = self.hosted.advance(
            step_listener=capture,
        )
        return update, capture

    @staticmethod
    def _play_committed(update: EngineUpdate, card_id: int) -> bool:
        """
        Return whether this update committed a manually played card.

        CardPlayedResult, MonsterSummonedResult, and SpellCastResult are
        canonically emitted later by EmitPlayResults. The action-log display
        results instead describe the successful Summon or Cast immediately,
        before Magic can create another choice request.
        """
        for record in update.log_records:
            for result in record.display_results:
                if (
                    isinstance(result, MonsterSummonedResult)
                    and result.monster_id == card_id
                    and result.is_played
                ):
                    return True

                if (
                    isinstance(result, SpellCastResult)
                    and result.card_id == card_id
                    and result.is_played
                ):
                    return True

        return False

    async def _emit_update(
        self,
        update: EngineUpdate,
        *,
        synchronize: bool,
        capture=None,
        present_request: bool = True,
    ) -> None:
        if capture is None:
            events, battle_logs = (
                self.hosted.adapter.translate_update(
                    update,
                    viewer_id=self.player_id,
                )
            )
        else:
            events, battle_logs = capture.render(
                update,
                synchronize=synchronize,
            )

        self.hosted.append_battle_logs(
            self.player_id,
            battle_logs,
        )

        await self.send_events(events)

        request = self._current_request()
        temporary_choice_active = isinstance(
            request,
            PendingChoiceRequest,
        )

        if (
            synchronize
            and capture is None
            and not temporary_choice_active
        ):
            await self.send_events(
                self.hosted.adapter.synchronization_events(self.player_id)
            )

        if request is not None and present_request:
            await self._present_request(request)

        if self.hosted.game.game_over:
            # Keep the session alive until the browser closes it after
            # handling the queued result event.
            await self.send_event(
                self.hosted.adapter.game_result_event(self.player_id)
            )

    # --------------------
    # Command handling
    # --------------------

    async def _handle_text_message(
        self,
        message: str,
    ) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError as exc:
            raise FatalProtocolError(
                "Invalid JSON payload"
            ) from exc

        if not isinstance(data, dict):
            raise FatalProtocolError(
                "WebSocket frame must contain a JSON object"
            )

        action_name = data.get('action')
        if not isinstance(action_name, str):
            raise FatalProtocolError(
                "Protocol message must contain a string action"
            )

        handlers = {
            'ping': self._handle_ping,
            'playMonster': self._handle_play_monster,
            'playSpell': self._handle_play_spell,
            'attack': self._handle_attack,
            'endTurn': self._handle_end_turn,
            'effectTarget': self._handle_effect_target,
            'cancelWaitingTarget': self._handle_cancel_waiting_target,
            'mulligan': self._handle_mulligan,
            'emote': self._handle_emote,
            'surrender': self._handle_surrender,
        }

        handler = handlers.get(action_name)
        if handler is None:
            raise FatalProtocolError(
                f"Unknown command {action_name!r}",
                translation_args=(action_name,),
            )

        await handler(data)

    async def _handle_ping(self, data: dict) -> None:
        _validate_fields(data, required={'action'})

    async def _handle_play_monster(
        self,
        data: dict,
    ) -> None:
        _validate_fields(
            data,
            required={'action', 'id', 'x'},
        )

        card_id = _parse_decimal_int(
            data['id'],
            field_name='id',
        )
        board_pos = _parse_decimal_int(
            data['x'],
            field_name='x',
        )

        if not 0 <= board_pos <= 3:
            raise FatalProtocolError(
                "Monster board position must be between 0 and 3"
            )

        entity = self._require_entity(card_id)
        if not isinstance(entity, Monster):
            raise FatalProtocolError(
                f"Entity {card_id} is not a Monster"
            )

        request = self._current_request()
        if not isinstance(request, PendingPlayerActionRequest):
            await self._reject_play(
                entity,
            )
            return

        response = PlayerActionResponse(
            request_id=request.request_id,
            player_id=self.player_id,
            action=PlayMonster(
                card_id=card_id,
                board_slot=board_pos,
            ),
        )
        ok, _ = self.hosted.runner.provide_input(response)

        if not ok:
            await self._reject_play(
                entity,
            )
            return

        update, capture = self._advance_with_capture()
        pending = self._current_request()

        was_played = self._play_committed(update, card_id)

        if (
            isinstance(pending, PendingChoiceRequest)
            and not was_played
        ):
            self.hosted.pending_play = PendingPlay(
                request_id=pending.request_id,
                card_id=card_id,
                board_pos=board_pos,
            )
        else:
            self.hosted.pending_play = None

        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )

    async def _handle_play_spell(
        self,
        data: dict,
    ) -> None:
        _validate_fields(
            data,
            required={'action', 'id'},
        )

        card_id = _parse_decimal_int(
            data['id'],
            field_name='id',
        )
        entity = self._require_entity(card_id)

        if not isinstance(entity, Spell):
            raise FatalProtocolError(
                f"Entity {card_id} is not a Spell"
            )

        request = self._current_request()
        if not isinstance(request, PendingPlayerActionRequest):
            await self._reject_play(entity)
            return

        response = PlayerActionResponse(
            request_id=request.request_id,
            player_id=self.player_id,
            action=PlaySpell(card_id=card_id),
        )
        ok, _ = self.hosted.runner.provide_input(response)

        if not ok:
            await self._reject_play(entity)
            return

        update, capture = self._advance_with_capture()
        pending = self._current_request()

        was_played = self._play_committed(update, card_id)

        if (
            isinstance(pending, PendingChoiceRequest)
            and not was_played
        ):
            self.hosted.pending_play = PendingPlay(
                request_id=pending.request_id,
                card_id=card_id,
                board_pos=None,
            )
        else:
            self.hosted.pending_play = None

        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )

    async def _reject_play(
        self,
        card: Monster | Spell,
    ) -> None:
        await self.send_event({
            'action': 'getPlayCardRejected',
            'cardId': card.id,
        })
        await self._restore_after_rejection()

    async def _handle_attack(
        self,
        data: dict,
    ) -> None:
        _validate_fields(
            data,
            required={
                'action',
                'idMonster',
                'idTarget',
            },
        )

        attacker_id = _parse_decimal_int(
            data['idMonster'],
            field_name='idMonster',
        )
        encoded_target = _parse_decimal_int(
            data['idTarget'],
            field_name='idTarget',
            allow_negative=True,
        )

        attacker = self._require_entity(attacker_id)
        if not isinstance(attacker, Monster):
            raise FatalProtocolError(
                f"Entity {attacker_id} is not a Monster"
            )

        if encoded_target < 0:
            raw_player_id = -encoded_target
            if raw_player_id not in (1, 2):
                raise FatalProtocolError(
                    f"Invalid player target {encoded_target}"
                )

            defender_id = PlayerId(raw_player_id)

        else:
            if encoded_target in (1, 2):
                raise FatalProtocolError(
                    "Players must use negative target IDs"
                )

            self._require_entity(encoded_target)
            defender_id = encoded_target

        request = self._current_request()
        if not isinstance(request, PendingPlayerActionRequest):
            await self._reject_generic_action()
            return

        response = PlayerActionResponse(
            request_id=request.request_id,
            player_id=self.player_id,
            action=Attack(
                attacker_id=attacker_id,
                defender_id=defender_id,
            ),
        )
        ok, _ = self.hosted.runner.provide_input(response)

        if not ok:
            await self._reject_generic_action()
            return

        await self.send_event({
            'action': 'getAttackDelock',
            'attackMonster': attacker_id,
            'targetId': encoded_target,
        })

        update, capture = self._advance_with_capture()
        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )

    async def _handle_end_turn(
        self,
        data: dict,
    ) -> None:
        _validate_fields(data, required={'action'})

        request = self._current_request()
        if not isinstance(request, PendingPlayerActionRequest):
            await self._reject_generic_action()
            return

        response = PlayerActionResponse(
            request_id=request.request_id,
            player_id=self.player_id,
            action=EndTurn(),
        )
        ok, _ = self.hosted.runner.provide_input(response)

        if not ok:
            await self._reject_generic_action()
            return

        update, capture = self._advance_with_capture()
        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )

    async def _reject_generic_action(self) -> None:
        await self.send_event({
            'action': 'getTempCancel',
        })
        await self._restore_after_rejection()

    async def _restore_after_rejection(self) -> None:
        request = self._current_request()
        if isinstance(request, PendingChoiceRequest):
            await self._present_request(request)
            return

        await self.send_events(
            self.hosted.adapter.synchronization_events(
                self.player_id
            )
        )

    async def _handle_effect_target(
        self,
        data: dict,
    ) -> None:
        _validate_fields(
            data,
            required={'action', 'idTarget'},
        )

        encoded_target = _parse_decimal_int(
            data['idTarget'],
            field_name='idTarget',
            allow_negative=True,
        )

        request = self._current_request()
        if not isinstance(request, PendingChoiceRequest):
            await self._reject_generic_action()
            return

        _, choice_map = self._build_choice_event(request)

        if encoded_target not in choice_map:
            if not self._wire_target_is_possible(encoded_target):
                raise FatalProtocolError(
                    f"Impossible target ID {encoded_target}"
                )

            await self._handle_invalid_choice(request)
            return

        selected_id = choice_map[encoded_target]

        was_initial_play = (
            self.hosted.pending_play is not None
            and self.hosted.pending_play.request_id == request.request_id
        )

        response = ChoiceResponse(
            request_id=request.request_id,
            player_id=self.player_id,
            selected_option_ids=(selected_id,),
        )
        ok, _ = self.hosted.runner.provide_input(response)

        if not ok:
            await self._handle_invalid_choice(request)
            return

        if was_initial_play:
            self.hosted.pending_play = None
        else:
            await self.send_event({
                'action': 'getTempCancel',
            })

        update, capture = self._advance_with_capture()
        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )

    async def _handle_invalid_choice(
        self,
        request: PendingChoiceRequest,
    ) -> None:
        pending_play = self.hosted.pending_play
        is_initial_play = (
            pending_play is not None
            and pending_play.request_id == request.request_id
        )

        if is_initial_play and request.allow_cancel:
            response = ChoiceResponse(
                request_id=request.request_id,
                player_id=self.player_id,
                selected_option_ids=(),
            )
            ok, _ = self.hosted.runner.provide_input(
                response
            )
            if ok:
                self.hosted.pending_play = None
                await self.send_event({
                    'action': 'getTempCancel',
                })

                update, capture = self._advance_with_capture()
                await self._emit_update(
                    update,
                    synchronize=True,
                    capture=capture,
                )
                return

        await self.send_event({
            'action': 'getTempCancel',
        })
        await self._present_request(request)

    async def _handle_cancel_waiting_target(
        self,
        data: dict,
    ) -> None:
        _validate_fields(data, required={'action'})

        request = self._current_request()
        if not isinstance(request, PendingChoiceRequest):
            await self._reject_generic_action()
            return

        if not request.allow_cancel:
            await self.send_event({
                'action': 'getTempCancel',
            })
            await self._present_request(request)
            return

        response = ChoiceResponse(
            request_id=request.request_id,
            player_id=self.player_id,
            selected_option_ids=(),
        )
        ok, _ = self.hosted.runner.provide_input(response)

        if not ok:
            await self.send_event({
                'action': 'getTempCancel',
            })
            await self._present_request(request)
            return

        self.hosted.pending_play = None

        await self.send_event({
            'action': 'getTempCancel',
        })

        update, capture = self._advance_with_capture()
        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )

    async def _handle_mulligan(
        self,
        data: dict,
    ) -> None:
        _validate_fields(
            data,
            required={'action', 'ids'},
        )

        raw_ids = data['ids']
        if not isinstance(raw_ids, list):
            raise FatalProtocolError(
                "mulligan.ids must be an array"
            )

        request = self._current_request()
        if not isinstance(request, PendingMulliganRequest):
            raise FatalProtocolError(
                "No mulligan request is active"
            )

        offered = set(request.prompt.offered_card_ids)
        selected: list[int] = []
        seen: set[int] = set()

        for value in raw_ids:
            card_id = _parse_decimal_int(
                value,
                field_name='mulligan.ids[]',
            )

            if card_id not in offered:
                continue
            if card_id in seen:
                continue

            seen.add(card_id)
            selected.append(card_id)

        response = MulliganResponse(
            request_id=request.request_id,
            player_id=self.player_id,
            replace_card_ids=tuple(selected),
        )
        ok, reason = self.hosted.runner.provide_input(response)

        if not ok:
            raise FatalProtocolError(
                f"Mulligan response was rejected: {reason}"
            )

        await self.send_event({
            'action': 'getHideMulligan',
        })

        update, capture = self._advance_with_capture()
        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )

    async def _handle_emote(
        self,
        data: dict,
    ) -> None:
        _validate_fields(
            data,
            required={'action', 'id'},
        )

        emote_id = data['id']
        if not isinstance(emote_id, (str, int)):
            raise FatalProtocolError(
                "emote.id must be a string or integer"
            )

        if str(emote_id) != str(
            self.hosted.config.assets.default_emote_id
        ):
            return

        event = {
            'action': 'getEmote',
            'idUser': self.player_id.value,
            'emoteImage': (
                self.hosted.config.assets.default_emote_image
            ),
        }

        sessions = tuple(self.hosted.sessions.values())
        for session in sessions:
            try:
                await session.send_event(event)
            except ConnectionClosed:
                continue

    async def _handle_surrender(
        self,
        data: dict,
    ) -> None:
        _validate_fields(data, required={'action'})

        if (
            self.hosted.game.game_over
            or not self.hosted.game.setup_complete
        ):
            await self._reject_generic_action()
            return

        requests_to_remove = [
            request_id
            for request_id, request
            in self.hosted.game.pending_requests.items()
            if request.player_id is self.player_id
        ]
        for request_id in requests_to_remove:
            del self.hosted.game.pending_requests[request_id]

        player = self.hosted.game.player(self.player_id)
        opponent = player.opponent

        self.hosted.game.enqueue_actions(
            Kill(
                target=player,
                killer=opponent,
                skip_check_death_prevented=True,
            ),
            source=opponent,
        )

        update, capture = self._advance_with_capture()
        await self._emit_update(
            update,
            synchronize=True,
            capture=capture,
        )
