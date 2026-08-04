import json
import time
from dataclasses import dataclass
from typing import Iterable

from deltacards.actions.results import (
    AbilityTriggeredResult,
    ActionResult,
    AttackDeclaredResult,
    BoardSlotEnchantedResult,
    CardOverdrawnResult,
    CardRevealedResult,
    DodgeConsumedResult,
    EntityDamagedResult,
    EntityHealedResult,
    EnchantmentRemovedResult,
    MonsterKilledResult,
    MonsterSummonedResult,
    SpellCastResult,
)
from deltacards.engine.action_log import ActionLogRecord
from deltacards.engine.runner import EngineUpdate, GameRunner
from deltacards.model.cards import Card, Monster
from deltacards.model.enchantments import Enchantment
from deltacards.model.enums import PlayerId
from deltacards.model.player import Player
from deltacards.model.requests import (
    Attack,
    PendingPlayerActionRequest,
    PlayMonster,
    PlaySpell,
)
from deltacards.model.slots import BoardSlot
from deltacards.model.snapshots import (
    ArtifactSnapshot,
    CardSnapshot,
    EnchantmentSnapshot,
    MonsterSnapshot,
    PlayerSnapshot,
    SoulSnapshot,
)

from .config import (
    DEFAULT_GAME_TYPE,
    DEFAULT_PLAYER_LEVEL,
    DEFAULT_RANK,
    ServerConfig,
)
from .serializers import (
    ViewSerializer,
    json_text,
    wire_slot_id,
)


@dataclass(slots=True)
class FrontendState:
    """
    Frozen, viewer-specific projection of the state understood by game.js.

    Values stored here contain only ordinary JSON-compatible values. They do
    not retain references to mutable runtime cards or snapshots.
    """

    hand: list[dict]
    board: list[dict]

    hands_size: dict[str, int]
    decks_size: dict[str, int]
    golds: dict[str, int]
    golds_next_turn: dict[str, int]
    artifacts: dict[str, list[dict]]

    hp: dict[int, tuple[int, int]]
    souls: dict[int, dict]
    slots: dict[int, dict]
    dustpile: list[dict]

    turn: int
    visible_card_ids: frozenset[int]


@dataclass(slots=True)
class CapturedFrontendStep:
    update: EngineUpdate
    before: FrontendState
    after: FrontendState
    turn: int


class FrontendUpdateCapture:
    """
    Synchronous GameRunner step listener.

    State is serialized while the runner is paused between actions. Rendering
    into WebSocket messages happens later, after `.resolve_until_blocked()` has
    returned, so the listener never performs asynchronous I/O.
    """

    def __init__(
        self,
        *,
        adapter: 'FrontendAdapter',
        viewer_id: PlayerId,
    ):
        self.adapter = adapter
        self.viewer_id = viewer_id
        self.initial_state = adapter.frontend_state(viewer_id)
        self.last_state = self.initial_state
        self.steps: list[CapturedFrontendStep] = []

    def __call__(self, update: EngineUpdate) -> None:
        after = self.adapter.frontend_state(self.viewer_id)
        self.steps.append(
            CapturedFrontendStep(
                update=update,
                before=self.last_state,
                after=after,
                turn=after.turn,
            )
        )
        self.last_state = after

    def render(
        self,
        final_update: EngineUpdate,
        *,
        synchronize: bool,
    ) -> tuple[list[dict], list[dict]]:
        events: list[dict] = []
        battle_logs: list[dict] = []

        related_records = [
            record
            for step in self.steps
            for record in step.update.log_records
        ]

        emitted_state = self.initial_state

        for step in self.steps:
            step_events, step_logs = self.adapter.translate_update(
                step.update,
                viewer_id=self.viewer_id,
                related_records=related_records,
                turn_number=step.turn,
                include_side_effect_state_events=False,
                visible_card_ids=step.after.visible_card_ids,
            )

            # Coalesce state-only engine actions. If several silent actions
            # occurred, synchronize their combined state immediately before
            # the next presentation event.
            if (
                synchronize
                and step_events
                and emitted_state != step.before
            ):
                events.extend(
                    self.adapter.differential_synchronization_events(
                        emitted_state,
                        step.before,
                        viewer_id=self.viewer_id,
                        presentation_events=step_events,
                    )
                )
                emitted_state = step.before

            events.extend(step_events)
            battle_logs.extend(step_logs)

            if synchronize and step_events:
                events.extend(
                    self.adapter.differential_synchronization_events(
                        emitted_state,
                        step.after,
                        viewer_id=self.viewer_id,
                        presentation_events=step_events,
                    )
                )
                emitted_state = step.after

        # Flush any remaining state-only changes at the blocking boundary.
        if synchronize and emitted_state != self.last_state:
            events.extend(
                self.adapter.differential_synchronization_events(
                    emitted_state,
                    self.last_state,
                    viewer_id=self.viewer_id,
                )
            )

        # Send playability payload once when the engine has opened the next ordinary decision.
        if (
            synchronize
            and not final_update.game_over
            and any(
                isinstance(request, PendingPlayerActionRequest)
                and request.player_id is self.viewer_id
                for request in final_update.pending
            )
        ):
            events.append(
                self.adapter.playable_payload(self.viewer_id)
            )

        return events, battle_logs


class FrontendAdapter:
    def __init__(
        self,
        *,
        game_id: int,
        runner: GameRunner,
        config: ServerConfig,
        usernames: dict[PlayerId, str],
    ):
        self.game_id = game_id
        self.runner = runner
        self.game = runner.game
        self.config = config
        self.usernames = usernames

        self.views = ViewSerializer(
            game=self.game,
            assets=config.assets,
            usernames=usernames,
        )

    # ------------------------
    # General payload helpers
    # ------------------------

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    def _animation(
        self,
        name: str,
        **fields,
    ) -> list[dict]:
        if not self.config.presentation.emit_animation_events:
            return []

        return [{
            'action': 'getAnimation',
            'animation': name,
            'waitTime': self.config.presentation.wait_time(name),
            **fields,
        }]

    @staticmethod
    def _battle_log_event(battle_log: dict) -> dict:
        return {
            'action': 'getBattleLog',
            'battleLog': json_text(battle_log),
        }

    # --------------------
    # Playability
    # --------------------

    def playable_payload(
        self,
        viewer_id: PlayerId,
    ) -> dict:
        request = next((
            request
            for request in self.game.pending_requests.values()
            if (
                isinstance(request, PendingPlayerActionRequest)
                and request.player_id is viewer_id
            )
        ), None)

        if request is None:
            return {
                'action': 'getPlayableCards',
                'playableCards': json_text([]),
                'playableNoTargets': json_text([]),
                'playableTriggers': json_text([]),
                'availableAttackTargets': json_text({}),
            }

        playable_cards: list[int] = []
        playable_triggers: list[int] = []
        playable_no_targets: list[int] = []
        available_attack_targets: dict[str, list[int]] = {}

        viewer = self.game.player(viewer_id)

        for action in self.runner.legal_player_actions(viewer_id):
            if isinstance(action, (PlayMonster, PlaySpell)):
                if action.card_id not in playable_cards:
                    playable_cards.append(action.card_id)

                card = self.game.card(action.card_id)

                if (
                    card.has_need_condition()
                    and self.game.card_need_fulfilled(card)
                    and (card.id not in playable_triggers)
                ):
                    playable_triggers.append(card.id)

                if (
                    isinstance(action, PlayMonster)
                    and card.targets is not None
                    and not self.game.play_target_options(
                        card=card,
                        player=viewer,
                        pos=action.board_slot,
                    )
                    and card.id not in playable_no_targets
                ):
                    playable_no_targets.append(card.id)

            elif isinstance(action, Attack):
                if action.attacker_id not in playable_cards:
                    playable_cards.append(action.attacker_id)

                key = str(action.attacker_id)
                targets = available_attack_targets.setdefault(key, [])

                defender = self.game.entity(action.defender_id)
                if isinstance(defender, Player):
                    encoded_target = -int(defender.id)
                else:
                    encoded_target = int(defender.id)

                if encoded_target not in targets:
                    targets.append(encoded_target)

        return {
            'action': 'getPlayableCards',
            'playableCards': json_text(playable_cards),
            'playableNoTargets': json_text(playable_no_targets),
            'playableTriggers': json_text(playable_triggers),
            'availableAttackTargets': json_text(available_attack_targets),
        }

    # --------------------
    # Initial state
    # --------------------

    def connect_event(
        self,
        *,
        viewer_id: PlayerId,
        battle_logs: list[dict],
        waiting_card_range: dict | None = None,
    ) -> dict:
        viewer = self.game.player(viewer_id)
        opponent = viewer.opponent

        starting_player_id = next(
            player_id.value
            for player_id in (PlayerId.P1, PlayerId.P2)
            if self.game.player(player_id).is_first_turn
        )

        payload = {
            'action': 'connect',

            'you': json_text(self.views.connection_player_view(viewer)),
            'enemy': json_text(self.views.connection_player_view(opponent)),

            'handsSize': json_text(self.views.hands_size_view()),
            'decksSize': json_text(self.views.decks_size_view()),
            'golds': json_text(self.views.golds_view()),
            'goldsNextTurn': json_text(self.views.golds_next_turn_view()),

            'yourSoul': json_text(self.views.soul_view(viewer.soul)),
            'enemySoul': json_text(self.views.soul_view(opponent.soul)),

            'hand': json_text(self.views.hand_view(viewer)),
            'board': json_text(self.views.board_view()),
            'slots': json_text(self.views.slots_view()),

            'turn': self.game.turn,
            'userTurn': self.game.turn_player.id.value,
            'startingPlayerId': starting_player_id,

            'yourGroups': json_text([]),
            'yourMainGroup': json_text(None),
            'enemyGroups': json_text([]),
            'enemyMainGroup': json_text(None),

            'yourEmotes': json_text([
                self.views.emote_view(),
            ]),

            'idFight': 0,
            'gameType': DEFAULT_GAME_TYPE,
            'gameId': self.game_id,

            'totalTurnAnimationDuration': 0,
            'lockTime': 0,

            'yourAvatar': json_text(self.views.avatar_view()),
            'enemyAvatar': json_text(self.views.avatar_view()),

            'yourShinyAvatar': False,
            'enemyShinyAvatar': False,

            'yourProfileSkin': json_text(self.views.profile_skin_view()),
            'enemyProfileSkin': json_text(self.views.profile_skin_view()),

            'yourLevel': DEFAULT_PLAYER_LEVEL,
            'enemyLevel': DEFAULT_PLAYER_LEVEL,
            'yourRank': DEFAULT_RANK,
            'enemyRank': DEFAULT_RANK,

            'yourArtifacts': json_text([
                self.views.artifact_view(artifact)
                for artifact in viewer.artifacts
            ]),
            'enemyArtifacts': json_text([
                self.views.artifact_view(artifact)
                for artifact in opponent.artifacts
            ]),

            'isMulliganDone': self.game.setup_complete,

            'packetDate': self._now_ms(),
            'turnTime': 0,

            'dustpile': json_text(self.views.dustpile_view()),
            'battleLogs': json_text(battle_logs),
        }

        if waiting_card_range is not None:
            payload['waitingCardRange'] = json_text(
                waiting_card_range
            )

        payload.update({
            key: value
            for key, value in self.playable_payload(viewer_id).items()
            if key != 'action'
        })

        return payload

    def mulligan_event(
        self,
        offered_card_ids: Iterable[int],
    ) -> dict:
        return {
            'action': 'getShowMulligan',
            'hand': json_text([
                self.views.card_view(self.game.card(card_id))
                for card_id in offered_card_ids
            ]),
        }

    # --------------------
    # Synchronization
    # --------------------

    @staticmethod
    def _wire_copy(value):
        """
        Normalize enums and integer dictionary keys exactly as JSON does.

        This also guarantees that captured state contains no mutable engine objects.
        """
        return json.loads(json_text(value))

    @staticmethod
    def _event_json(event: dict, field: str):
        value = event.get(field)
        if isinstance(value, str):
            return json.loads(value)

        return value

    def frontend_state(
        self,
        viewer_id: PlayerId,
    ) -> FrontendState:
        hand = self._wire_copy(
            self.views.hand_view(self.game.player(viewer_id))
        )
        board = self._wire_copy(self.views.board_view())
        slot_views = self._wire_copy(self.views.slots_view())

        hp = {
            player_id.value: (
                self.game.player(player_id).hp,
                self.game.player(player_id).max_hp,
            )
            for player_id in (PlayerId.P1, PlayerId.P2)
        }

        souls = {
            player_id.value: self._wire_copy(
                self.views.soul_view(
                    self.game.player(player_id).soul
                )
            )
            for player_id in (PlayerId.P1, PlayerId.P2)
        }

        visible_card_ids = frozenset(
            int(entity.id)
            for entity in self.game.entities.values()
            if (
                isinstance(entity, Card)
                and self.views.card_is_visible(
                    entity,
                    viewer_id,
                )
            )
        )

        return FrontendState(
            hand=hand,
            board=board,
            hands_size=self._wire_copy(
                self.views.hands_size_view()
            ),
            decks_size=self._wire_copy(
                self.views.decks_size_view()
            ),
            golds=self._wire_copy(self.views.golds_view()),
            golds_next_turn=self._wire_copy(
                self.views.golds_next_turn_view()
            ),
            artifacts=self._wire_copy(
                self.views.artifacts_map_view()
            ),
            hp=hp,
            souls=souls,
            slots={
                int(slot['id']): slot
                for slot in slot_views
            },
            dustpile=self._wire_copy(
                self.views.dustpile_view()
            ),
            turn=self.game.turn,
            visible_card_ids=visible_card_ids,
        )

    def begin_update_capture(
        self,
        viewer_id: PlayerId,
    ) -> FrontendUpdateCapture:
        return FrontendUpdateCapture(
            adapter=self,
            viewer_id=viewer_id,
        )

    def differential_synchronization_events(
        self,
        before: FrontendState,
        after: FrontendState,
        *,
        viewer_id: PlayerId,
        presentation_events: Iterable[dict] = (),
    ) -> list[dict]:
        """
        Synchronize only frontend components that changed.

        Presentation events from the same step are taken into account so an
        accepted play, destruction, damage update, or Enchantment update
        doesn't receive a redundant destructive full refresh.
        """
        events: list[dict] = []
        presentation_events = list(presentation_events)

        presented_updated_cards: dict[int, dict] = {}
        presented_played_cards: dict[int, dict] = {}
        presented_destroyed_cards: set[int] = set()
        local_played_card_ids: set[int] = set()

        for event in presentation_events:
            action = event.get('action')

            if action == 'updateCard':
                card = self._event_json(event, 'card')
                if isinstance(card, dict):
                    presented_updated_cards[int(card['id'])] = card

            elif action == 'getMonsterPlayed':
                card = self._event_json(event, 'card')
                if isinstance(card, dict):
                    card_id = int(card['id'])
                    presented_played_cards[card_id] = card

                    if event.get('idPlayer') == viewer_id.value:
                        local_played_card_ids.add(card_id)

            elif action == 'getSpellPlayed':
                card = self._event_json(event, 'card')
                if (
                    isinstance(card, dict)
                    and event.get('idPlayer') == viewer_id.value
                ):
                    local_played_card_ids.add(int(card['id']))

            elif action == 'getMonsterDestroyed':
                presented_destroyed_cards.add(
                    int(event['monsterId'])
                )

        emitted_card_updates: set[int] = set()

        def append_card_update(card: dict) -> None:
            card_id = int(card['id'])
            if card_id in emitted_card_updates:
                return

            emitted_card_updates.add(card_id)
            events.append({
                'action': 'updateCard',
                'card': json_text(card),
            })

        # Hand ---------------------------------------------------------
        #
        # If membership is unchanged, update cards in place. If an
        # accepted play accounts for the sole removal, let its play event
        # remove the optimistic card. Full hand replacement is reserved for
        # additions, reordering, or otherwise unrepresented membership
        # changes.
        if before.hand != after.hand:
            hand_already_replaced = any(
                event.get('action') == 'getUpdateHand'
                and self._event_json(event, 'hand') == after.hand
                for event in presentation_events
            )

            if not hand_already_replaced:
                before_ids = [
                    int(card['id'])
                    for card in before.hand
                ]
                after_ids = [
                    int(card['id'])
                    for card in after.hand
                ]

                expected_after_ids = [
                    card_id
                    for card_id in before_ids
                    if card_id not in local_played_card_ids
                ]

                membership_accounted = (
                    expected_after_ids == after_ids
                )

                if membership_accounted:
                    before_by_id = {
                        int(card['id']): card
                        for card in before.hand
                    }

                    for card in after.hand:
                        card_id = int(card['id'])
                        if before_by_id.get(card_id) == card:
                            continue
                        if presented_updated_cards.get(card_id) == card:
                            continue

                        append_card_update(card)

                else:
                    events.append({
                        'action': 'getUpdateHand',
                        'hand': json_text(after.hand),
                    })

        # Board --------------------------------------------------------
        #
        # updateCard is sufficient for stat/status changes. A complete
        # board replacement is required only when topology changed and no
        # specific play/destruction event represents that transition.
        if before.board != after.board:
            board_already_replaced = any(
                event.get('action') == 'getUpdateBoard'
                and self._event_json(event, 'board') == after.board
                for event in presentation_events
            )

            if not board_already_replaced:
                before_by_id = {
                    int(card['id']): card
                    for card in before.board
                }
                after_by_id = {
                    int(card['id']): card
                    for card in after.board
                }

                before_ids = set(before_by_id)
                after_ids = set(after_by_id)

                added_ids = after_ids - before_ids
                removed_ids = before_ids - after_ids
                common_ids = before_ids & after_ids

                def layout(card: dict) -> tuple[int, int]:
                    return (
                        int(card['ownerId']),
                        int(card['boardPosition']),
                    )

                moved_ids = {
                    card_id
                    for card_id in common_ids
                    if (
                        layout(before_by_id[card_id])
                        != layout(after_by_id[card_id])
                    )
                }

                additions_accounted = all(
                    card_id in presented_played_cards
                    and (
                        layout(presented_played_cards[card_id])
                        == layout(after_by_id[card_id])
                    )
                    for card_id in added_ids
                )
                removals_accounted = (
                    removed_ids <= presented_destroyed_cards
                )

                topology_accounted = (
                    not moved_ids
                    and additions_accounted
                    and removals_accounted
                )

                if not topology_accounted:
                    events.append({
                        'action': 'getUpdateBoard',
                        'board': json_text(after.board),
                    })

                else:
                    for card in after.board:
                        card_id = int(card['id'])
                        previous = before_by_id.get(card_id)

                        if previous == card:
                            continue
                        if presented_updated_cards.get(card_id) == card:
                            continue
                        if presented_played_cards.get(card_id) == card:
                            continue

                        append_card_update(card)

        # Hand/deck/Gold/Artifact statistics --------------------------
        stats_changed = any((
            before.hands_size != after.hands_size,
            before.decks_size != after.decks_size,
            before.golds != after.golds,
            before.golds_next_turn != after.golds_next_turn,
            before.artifacts != after.artifacts,
        ))

        if stats_changed:
            stats_already_updated = any(
                event.get('action') == 'getPlayersStats'
                and (
                    self._event_json(event, 'handsSize')
                    == after.hands_size
                )
                and (
                    self._event_json(event, 'decksSize')
                    == after.decks_size
                )
                and (
                    self._event_json(event, 'golds')
                    == after.golds
                )
                and (
                    self._event_json(event, 'goldsNextTurn')
                    == after.golds_next_turn
                )
                and (
                    self._event_json(event, 'artifacts')
                    == after.artifacts
                )
                for event in presentation_events
            )

            if not stats_already_updated:
                events.append({
                    'action': 'getPlayersStats',
                    'handsSize': json_text(after.hands_size),
                    'decksSize': json_text(after.decks_size),
                    'golds': json_text(after.golds),
                    'goldsNextTurn': json_text(
                        after.golds_next_turn
                    ),
                    'artifacts': json_text(after.artifacts),
                })

        # Player HP ----------------------------------------------------
        for player_id in sorted(after.hp):
            if before.hp.get(player_id) == after.hp[player_id]:
                continue

            hp, max_hp = after.hp[player_id]
            hp_already_updated = any(
                event.get('action') == 'getUpdatePlayerHp'
                and event.get('playerId') == player_id
                and event.get('hp') == hp
                and event.get('maxHp') == max_hp
                for event in presentation_events
            )

            if not hp_already_updated:
                events.append({
                    'action': 'getUpdatePlayerHp',
                    'playerId': player_id,
                    'hp': hp,
                    'maxHp': max_hp,
                    'animation': False,
                    'isDamage': False,
                })

        # Souls --------------------------------------------------------
        for player_id in sorted(after.souls):
            soul = after.souls[player_id]
            if before.souls.get(player_id) == soul:
                continue

            soul_already_updated = any(
                event.get('action') == 'getUpdateSoul'
                and event.get('idPlayer') == player_id
                and self._event_json(event, 'soul') == soul
                for event in presentation_events
            )

            if not soul_already_updated:
                events.append({
                    'action': 'getUpdateSoul',
                    'idPlayer': player_id,
                    'soul': json_text(soul),
                })

        # Enchantments -------------------------------------------------
        for slot_id in sorted(
            set(before.slots) | set(after.slots)
        ):
            slot = after.slots.get(slot_id)
            if slot is None:
                continue
            if before.slots.get(slot_id) == slot:
                continue

            slot_already_updated = any(
                event.get('action') == 'getUpdateSlot'
                and self._event_json(event, 'slot') == slot
                for event in presentation_events
            )

            if not slot_already_updated:
                events.append({
                    'action': 'getUpdateSlot',
                    'slot': json_text(slot),
                })

        # Dustpile -----------------------------------------------------
        if before.dustpile != after.dustpile:
            dustpile_already_updated = any(
                event.get('action') == 'getUpdateDustpile'
                and (
                    self._event_json(event, 'dustpile')
                    == after.dustpile
                )
                for event in presentation_events
            )

            if not dustpile_already_updated:
                events.append({
                    'action': 'getUpdateDustpile',
                    'dustpile': json_text(after.dustpile),
                })

        # Global turn display -----------------------------------------
        if before.turn != after.turn:
            turn_already_updated = any(
                (
                    event.get('action') == 'getTurn'
                    and event.get('turn') == after.turn
                )
                or (
                    event.get('action') == 'getTurnStart'
                    and event.get('numTurn') == after.turn
                )
                for event in presentation_events
            )

            if not turn_already_updated:
                events.append({
                    'action': 'getTurn',
                    'turn': after.turn,
                })

        return events

    def synchronization_events(
        self,
        viewer_id: PlayerId,
        *,
        include_playability: bool = True,
    ) -> list[dict]:
        viewer = self.game.player(viewer_id)

        events: list[dict] = [
            {
                'action': 'getUpdateHand',
                'hand': json_text(self.views.hand_view(viewer)),
            },
            {
                'action': 'getUpdateBoard',
                'board': json_text(self.views.board_view()),
            },
            {
                'action': 'getPlayersStats',
                'handsSize': json_text(
                    self.views.hands_size_view()
                ),
                'decksSize': json_text(
                    self.views.decks_size_view()
                ),
                'golds': json_text(self.views.golds_view()),
                'goldsNextTurn': json_text(
                    self.views.golds_next_turn_view()
                ),
                'artifacts': json_text(
                    self.views.artifacts_map_view()
                ),
            },
        ]

        for player_id in (PlayerId.P1, PlayerId.P2):
            player = self.game.player(player_id)
            events.append({
                'action': 'getUpdatePlayerHp',
                'playerId': player.id.value,
                'hp': player.hp,
                'maxHp': player.max_hp,
                'animation': False,
                'isDamage': False,
            })
            events.append({
                'action': 'getUpdateSoul',
                'idPlayer': player.id.value,
                'soul': json_text(
                    self.views.soul_view(player.soul)
                ),
            })

        for player_id in (PlayerId.P1, PlayerId.P2):
            for slot in self.game.player(player_id).board_slots:
                events.append({
                    'action': 'getUpdateSlot',
                    'slot': json_text(self.views.slot_view(slot)),
                })

        events.extend([
            {
                'action': 'getUpdateDustpile',
                'dustpile': json_text(
                    self.views.dustpile_view()
                ),
            },
            {
                'action': 'getTurn',
                'turn': self.game.turn,
            },
        ])

        if include_playability:
            events.append(self.playable_payload(viewer_id))

        return events

    # --------------------
    # Action-log helpers
    # --------------------

    @staticmethod
    def _descendants(
        root: ActionLogRecord,
        records: list[ActionLogRecord],
    ) -> list[ActionLogRecord]:
        return [
            record
            for record in records
            if (
                record.id == root.id
                or (
                    record.group_id == root.group_id
                    and record.parent_id == root.id
                )
            )
        ]

    @staticmethod
    def _result_target_snapshots(
        result: ActionResult,
    ) -> tuple[list[CardSnapshot], list[PlayerSnapshot]]:
        cards: list[CardSnapshot] = []
        players: list[PlayerSnapshot] = []

        if isinstance(result, EntityDamagedResult):
            if isinstance(result.target, MonsterSnapshot):
                cards.append(result.target)
            elif isinstance(result.target, PlayerSnapshot):
                players.append(result.target)

        elif isinstance(result, EntityHealedResult):
            if isinstance(result.target, MonsterSnapshot):
                cards.append(result.target)
            elif isinstance(result.target, PlayerSnapshot):
                players.append(result.target)

        elif isinstance(result, MonsterKilledResult):
            cards.append(result.monster)

        elif isinstance(result, MonsterSummonedResult):
            cards.append(result.monster)

        elif isinstance(result, CardOverdrawnResult):
            cards.append(result.card)

        return cards, players

    def _affected_entities(
        self,
        *,
        root: ActionLogRecord,
        records: list[ActionLogRecord],
        source_id: int,
        viewer_id: PlayerId,
        visible_card_ids: frozenset[int] | None = None,
    ) -> tuple[list[int], list[int], list[int]]:
        affected_cards: list[int] = []
        affected_slots: list[int] = []
        affected_players: list[int] = []

        for record in self._descendants(root, records):
            candidate_ids = list(record.affected_ids)

            for result in record.results:
                if isinstance(result, EntityDamagedResult):
                    candidate_ids.append(int(result.target_id))
                elif isinstance(result, EntityHealedResult):
                    candidate_ids.append(int(result.target_id))
                elif isinstance(result, MonsterKilledResult):
                    candidate_ids.append(result.monster_id)
                elif isinstance(result, MonsterSummonedResult):
                    candidate_ids.append(result.monster_id)
                elif isinstance(result, BoardSlotEnchantedResult):
                    affected_slots.append(
                        wire_slot_id(
                            result.slot.controller_id,
                            result.slot.pos,
                        )
                    )
                elif isinstance(result, EnchantmentRemovedResult):
                    affected_slots.append(
                        wire_slot_id(
                            result.slot.controller_id,
                            result.slot.pos,
                        )
                    )

            for entity_id in candidate_ids:
                if entity_id == source_id:
                    continue

                entity = self.game.entity(entity_id)

                if isinstance(entity, Player):
                    if entity.id not in affected_players:
                        affected_players.append(entity.id)

                elif isinstance(entity, BoardSlot):
                    slot_id = wire_slot_id(
                        entity.controller_id,
                        entity.pos,
                    )
                    if slot_id not in affected_slots:
                        affected_slots.append(slot_id)

                elif isinstance(entity, Enchantment):
                    slot = self.game.entity(entity.slot_id)
                    slot_id = wire_slot_id(
                        slot.controller_id,
                        slot.pos,
                    )
                    if slot_id not in affected_slots:
                        affected_slots.append(slot_id)

                elif isinstance(entity, Card):
                    if visible_card_ids is None:
                        visible = self.views.card_is_visible(
                            entity,
                            viewer_id,
                        )
                    else:
                        visible = entity.id in visible_card_ids

                    if (
                        visible
                        and entity.id not in affected_cards
                    ):
                        affected_cards.append(entity.id)

        return (
            affected_cards,
            affected_slots,
            affected_players,
        )

    def _ability_targets(
        self,
        *,
        root: ActionLogRecord,
        records: list[ActionLogRecord],
        source_id: int,
        viewer_id: PlayerId,
    ) -> tuple[list[dict], list[dict]]:
        target_cards: list[dict] = []
        target_players: list[dict] = []
        seen_cards: set[int] = set()
        seen_players: set[PlayerId] = set()

        for record in self._descendants(root, records):
            for result in record.results:
                cards, players = self._result_target_snapshots(result)

                for card in cards:
                    if card.id == source_id:
                        continue
                    if card.id in seen_cards:
                        continue
                    if not self.views.card_is_visible(card, viewer_id):
                        continue

                    seen_cards.add(card.id)
                    target_cards.append(
                        self.views.card_view(card)
                    )

                for player in players:
                    if player.id in seen_players:
                        continue

                    seen_players.add(player.id)
                    target_players.append(
                        self.views.battle_player_view(player)
                    )

        return target_cards, target_players

    # ---------------------
    # Ability presentation
    # ---------------------

    def _ability_source_event(
        self,
        *,
        result: AbilityTriggeredResult,
        record: ActionLogRecord,
        records: list[ActionLogRecord],
        viewer_id: PlayerId,
        visible_card_ids: frozenset[int] | None = None,
    ) -> tuple[dict | None, dict | None]:
        if not any(
            descendant.id != record.id
            for descendant in self._descendants(record, records)
        ):
            return None, None

        affected, affected_slots, affected_players = (
            self._affected_entities(
                root=record,
                records=records,
                source_id=int(result.entity_id),
                viewer_id=viewer_id,
                visible_card_ids=visible_card_ids,
            )
        )

        common = {
            'affecteds': json_text(affected),
            'affectedSlots': json_text(affected_slots),
            'waitTime': self.config.presentation.wait_time('EFFECT_WAIT'),
        }

        for index, player_id in enumerate(
            affected_players[:2],
            start=1,
        ):
            common[f'playerAffected{index}'] = int(player_id)

        source = result.entity
        event: dict | None = None
        battle_log: dict | None = None

        target_cards, target_players = self._ability_targets(
            root=record,
            records=records,
            source_id=int(result.entity_id),
            viewer_id=viewer_id,
        )

        if isinstance(source, CardSnapshot):
            event = {
                'action': 'getDoingEffect',
                'card': json_text(self.views.card_view(source)),
                **common,
            }
            battle_log = {
                'battleLogType': 'CARD_EFFECT',
                'playerId': source.controller_id.value,
                'cardActor': self.views.card_view(source),
                'targetCards': target_cards,
                'targetPlayers': target_players,
            }

        elif isinstance(source, SoulSnapshot):
            event = {
                'action': 'getSoulDoingEffect',
                'playerId': source.controller_id.value,
                **common,
            }
            battle_log = {
                'battleLogType': 'SOUL_EFFECT',
                'playerId': source.controller_id.value,
                'playerActor': {
                    'id': source.controller_id.value,
                    'soul': self.views.soul_view(source),
                },
                'targetCards': target_cards,
                'targetPlayers': target_players,
            }

        elif isinstance(source, ArtifactSnapshot):
            artifact_view = self.views.artifact_view(source)

            event = {
                'action': 'getArtifactDoingEffect',
                'playerId': source.controller_id.value,
                'artifactId': artifact_view['id'],
                **common,
            }
            battle_log = {
                'battleLogType': 'ARTIFACT_EFFECT',
                'playerId': source.controller_id.value,
                'artifactActor': {
                    'image': artifact_view['image'],
                },
                'targetCards': target_cards,
                'targetPlayers': target_players,
            }

        elif isinstance(source, EnchantmentSnapshot):
            slot = self.game.entity(source.slot_id)
            event = {
                'action': 'getEnchantDoingEffect',
                'slotId': wire_slot_id(
                    slot.controller_id,
                    slot.pos,
                ),
                **common,
            }

            battle_log = {
                'battleLogType': 'ENCHANT_EFFECT',
                'playerId': source.controller_id.value,
                'enchantActor': {
                    'name': self.views.enchantment_view(source)['name'],
                },
                'targetCards': target_cards,
                'targetPlayers': target_players,
            }

        return event, battle_log

    # --------------------
    # Result translation
    # --------------------

    def _result_events_and_logs(
        self,
        *,
        result: ActionResult,
        viewer_id: PlayerId,
    ) -> tuple[list[dict], list[dict]]:
        events: list[dict] = []
        logs: list[dict] = []

        if isinstance(result, CardRevealedResult):
            events.append({
                'action': 'getShowCard',
                'idPlayer': result.card.controller_id.value,
                'card': json_text(self.views.card_view(result.card)),
                'waitTime': self.config.presentation.wait_time('SHOW_CARD_WAIT'),
            })

        elif isinstance(result, CardOverdrawnResult):
            events.append({
                'action': 'getCardDestroyedHandFull',
                'card': json_text(self.views.card_view(result.card)),
                'waitTime': self.config.presentation.wait_time('OVERDRAW_WAIT'),
            })

            logs.append({
                'battleLogType': 'BURN',
                'playerId': result.player_id.value,
                'cardActor': self.views.card_view(result.card),
                'targetCards': [],
                'targetPlayers': [],
            })

        elif isinstance(result, MonsterSummonedResult):
            if result.is_played:
                events.append({
                    'action': 'getMonsterPlayed',
                    'idPlayer': result.player_id.value,
                    'x': result.monster.pos,
                    'card': json_text(self.views.card_view(result.monster)),
                    'waitTime': self.config.presentation.wait_time('MONSTER_PLAY_WAIT'),
                })

                log = {
                    'battleLogType': 'PLAY_MONSTER',
                    'playerId': result.player_id.value,
                    'cardActor': self.views.card_view(result.monster),
                    'targetCards': [],
                    'targetPlayers': [],
                }

                if isinstance(result.target, CardSnapshot):
                    if self.views.card_is_visible(
                        result.target,
                        viewer_id,
                    ):
                        log['targetCards'] = [
                            self.views.card_view(result.target)
                        ]

                elif isinstance(result.target, PlayerSnapshot):
                    log['targetPlayers'] = [
                        self.views.battle_player_view(result.target)
                    ]

                logs.append(log)

        elif isinstance(result, SpellCastResult):
            if result.is_played:
                events.append({
                    'action': 'getSpellPlayed',
                    'idPlayer': result.player_id.value,
                    'card': json_text(self.views.card_view(result.card)),
                    'waitTime': self.config.presentation.wait_time('SPELL_PLAY_WAIT'),
                })
                events.extend(self._animation('SPELL'))

            else:
                events.append({
                    'action': 'getShowCard',
                    'idPlayer': result.player_id.value,
                    'card': json_text(self.views.card_view(result.card)),
                    'waitTime': self.config.presentation.wait_time('SHOW_CARD_WAIT'),
                })

        elif isinstance(result, AttackDeclaredResult):
            if isinstance(result.defender, MonsterSnapshot):
                events.append({
                    'action': 'getFight',
                    'attackMonster': result.attacker_id,
                    'defendMonster': result.defender_id,
                    'dmgMonster': result.attacker.attack,
                    'waitTime': self.config.presentation.wait_time('COMBAT_WAIT'),
                })
                logs.append({
                    'battleLogType': 'ATTACK_MONSTER',
                    'playerId': result.attacker.controller_id.value,
                    'cardActor': self.views.card_view(result.attacker),
                    'targetCards': [
                        self.views.card_view(result.defender)
                    ],
                    'targetPlayers': [],
                })

            elif isinstance(result.defender, PlayerSnapshot):
                events.append({
                    'action': 'getFightPlayer',
                    'attackMonster': result.attacker_id,
                    'defendPlayer': result.defender.id.value,
                    'dmgMonster': result.attacker.attack,
                    'waitTime': self.config.presentation.wait_time('COMBAT_WAIT'),
                })
                logs.append({
                    'battleLogType': 'ATTACK_PLAYER',
                    'playerId': result.attacker.controller_id.value,
                    'cardActor': self.views.card_view(result.attacker),
                    'targetCards': [],
                    'targetPlayers': [
                        self.views.battle_player_view(result.defender)
                    ],
                })

        elif isinstance(result, EntityDamagedResult):
            if result.amount >= 7:
                events.extend(self._animation('BIG_DAMAGE'))

            if isinstance(result.target, MonsterSnapshot):
                events.extend(self._animation(
                    'HP_STAT',
                    target='MONSTER',
                    idTarget=result.target_id,
                    value=-result.amount,
                ))
                events.append({
                    'action': 'updateCard',
                    'card': json_text(self.views.card_view(result.target)),
                })

            elif isinstance(result.target, PlayerSnapshot):
                events.extend(self._animation(
                    'HP_STAT',
                    target='PLAYER',
                    idTarget=result.target_id.value,
                    value=-result.amount,
                ))
                events.append({
                    'action': 'getUpdatePlayerHp',
                    'playerId': result.target_id.value,
                    'hp': result.target.hp,
                    'maxHp': result.target.max_hp,
                    'animation': True,
                    'isDamage': True,
                })

        elif isinstance(result, EntityHealedResult):
            if isinstance(result.target, MonsterSnapshot):
                events.extend(self._animation(
                    'HEAL',
                    target='MONSTER',
                    idTarget=result.target_id,
                ))
                if result.amount != 0:
                    events.extend(self._animation(
                        'HP_STAT',
                        target='MONSTER',
                        idTarget=result.target_id,
                        value=result.amount,
                    ))

                events.append({
                    'action': 'updateCard',
                    'card': json_text(self.views.card_view(result.target)),
                })

            elif isinstance(result.target, PlayerSnapshot):
                events.extend(self._animation(
                    'HEAL',
                    target='PLAYER',
                    idTarget=result.target_id.value,
                ))
                if result.amount != 0:
                    events.extend(self._animation(
                        'HP_STAT',
                        target='PLAYER',
                        idTarget=result.target_id.value,
                        value=result.amount,
                    ))

                events.append({
                    'action': 'getUpdatePlayerHp',
                    'playerId': result.target_id.value,
                    'hp': result.target.hp,
                    'maxHp': result.target.max_hp,
                    'animation': True,
                    'isDamage': False,
                })

        elif isinstance(result, DodgeConsumedResult):
            events.append({
                'action': 'updateCard',
                'card': json_text(self.views.card_view(result.monster)),
            })

        elif isinstance(result, MonsterKilledResult):
            events.append({
                'action': 'getMonsterDestroyed',
                'monsterId': result.monster_id,
            })
            logs.append({
                'battleLogType': 'DEATH',
                'playerId': result.monster.controller_id.value,
                'cardActor': self.views.card_view(result.monster),
                'targetCards': [],
                'targetPlayers': [],
            })

        elif isinstance(result, BoardSlotEnchantedResult):
            events.append({
                'action': 'getUpdateSlot',
                'slot': json_text(
                    self.views.slot_snapshot_view(
                        result.slot,
                        result.enchantment,
                    )
                ),
            })

        elif isinstance(result, EnchantmentRemovedResult):
            events.append({
                'action': 'getUpdateSlot',
                'slot': json_text(
                    self.views.slot_snapshot_view(
                        result.slot,
                        None,
                    )
                ),
            })

        return events, logs

    def _record_side_effect_events(
        self,
        record: ActionLogRecord,
        viewer_id: PlayerId,
        *,
        include_state_events: bool = True,
    ) -> list[dict]:
        events: list[dict] = []

        if record.action_name in ('Silence', 'Paralyze'):
            animation = (
                'SILENCE'
                if record.action_name == 'Silence'
                else 'FREEZE'
            )

            for entity_id in record.affected_ids:
                entity = self.game.entity(entity_id)
                if isinstance(entity, Monster):
                    events.extend(self._animation(
                        animation,
                        idTarget=entity.id,
                    ))
                    if include_state_events:
                        events.append({
                            'action': 'updateCard',
                            'card': json_text(
                                self.views.card_view(entity)
                            ),
                        })

            return events

        if not include_state_events:
            return events

        if record.action_name in {
            'Buff',
            'SetStats',
            'SetBaseStats',
            'SwapStats',
            'HalveStats',
            'AddKeyword',
            'RemoveKeyword',
            'SetStatus',
            'RemoveStatus',
            'RemoveNegativeEffects',
            'RefreshAttacks',
            'ToggleAbility',
        }:
            for entity_id in record.affected_ids:
                entity = self.game.entity(entity_id)

                if (
                    isinstance(entity, Card)
                    and self.views.card_is_visible(
                        entity,
                        viewer_id,
                    )
                ):
                    events.append({
                        'action': 'updateCard',
                        'card': json_text(self.views.card_view(entity)),
                    })

        elif record.action_name == 'UpdateEnchantmentCounter':
            for entity_id in record.affected_ids:
                entity = self.game.entity(entity_id)
                if isinstance(entity, Enchantment):
                    slot = self.game.entity(entity.slot_id)
                    events.append({
                        'action': 'getUpdateSlot',
                        'slot': json_text(self.views.slot_view(slot)),
                    })

        return events

    # ----------------------------
    # Complete update translation
    # ----------------------------

    def translate_update(
        self,
        update: EngineUpdate,
        *,
        viewer_id: PlayerId,
        related_records: list[ActionLogRecord] | None = None,
        turn_number: int | None = None,
        include_side_effect_state_events: bool = True,
        visible_card_ids: frozenset[int] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        events: list[dict] = []
        battle_logs: list[dict] = []

        records = update.log_records
        context_records = (
            records
            if related_records is None
            else related_records
        )
        seen_results: set[int] = set()

        # Overdraw already has its own public reveal-and-destroy presentation.
        # Some engine paths also emit a CardRevealedResult for the same card;
        # avoid showing the card twice in that case.
        all_results = [
            result
            for record in context_records
            for result in record.results
        ]
        all_results.extend(update.results)
        overdrawn_card_ids = {
            result.card.id
            for result in all_results
            if isinstance(result, CardOverdrawnResult)
        }

        for record in records:
            seen_results.update(
                id(result)
                for result in record.results
            )

            if record.action_name == 'PlayerEndTurnAction':
                if record.source_id in self.game.players:
                    events.append({
                        'action': 'getTurnEnd',
                        'idPlayer': record.source_id.value,
                    })

            elif record.action_name == 'PlayerStartTurnAction':
                if record.source_id in self.game.players:
                    events.append({
                        'action': 'getTurnStart',
                        'idPlayer': record.source_id.value,
                        'numTurn': (
                            self.game.turn
                            if turn_number is None
                            else turn_number
                        ),
                        'packetDate': self._now_ms(),
                        'turnTime': 0,
                    })

            for result in record.display_results:
                if (
                    isinstance(result, CardRevealedResult)
                    and result.card.id in overdrawn_card_ids
                ):
                    continue

                if isinstance(result, AbilityTriggeredResult):
                    event, battle_log = (
                        self._ability_source_event(
                            result=result,
                            record=record,
                            records=context_records,
                            viewer_id=viewer_id,
                            visible_card_ids=visible_card_ids,
                        )
                    )

                    if event is not None:
                        events.append(event)

                    if battle_log is not None:
                        battle_logs.append(battle_log)
                        events.append(
                            self._battle_log_event(battle_log)
                        )

                    continue

                result_events, result_logs = (
                    self._result_events_and_logs(
                        result=result,
                        viewer_id=viewer_id,
                    )
                )
                events.extend(result_events)

                for battle_log in result_logs:
                    battle_logs.append(battle_log)
                    events.append(
                        self._battle_log_event(battle_log)
                    )

            events.extend(
                self._record_side_effect_events(
                    record,
                    viewer_id,
                    include_state_events=include_side_effect_state_events,
                )
            )

        for result in update.results:
            if id(result) in seen_results:
                continue

            if isinstance(result, AbilityTriggeredResult):
                continue

            if (
                isinstance(result, CardRevealedResult)
                and result.card.id in overdrawn_card_ids
            ):
                continue

            result_events, result_logs = (
                self._result_events_and_logs(
                    result=result,
                    viewer_id=viewer_id,
                )
            )
            events.extend(result_events)

            for battle_log in result_logs:
                battle_logs.append(battle_log)
                events.append(
                    self._battle_log_event(battle_log)
                )

        return events, battle_logs

    # --------------------
    # Game end screen
    # --------------------

    def game_result_event(
        self,
        viewer_id: PlayerId,
    ) -> dict:
        winner_id = self.game.winner_id()
        viewer = self.game.player(viewer_id)

        common = {
            'gameType': DEFAULT_GAME_TYPE,

            'golds': viewer.gold,
            'oldGold': viewer.gold,
            'queueGoldBonus': 0,

            'oldXp': 0,
            'newXp': 0,
            'oldJaugeSize': 100,
            'jaugeSize': 100,
            'xpUntilNextLevel': 100,
            'nbLevelPassed': 0,

            'oldDivision': DEFAULT_RANK,
            'newDivision': DEFAULT_RANK,
        }

        if winner_id is viewer_id:
            return {
                'action': 'getVictory',
                **common,
                'disconnected': False,
                'isDonator': False,
            }

        if winner_id is not None:
            return {
                'action': 'getDefeat',
                **common,
                'endType': 'NORMAL',
                'soul': viewer.soul.__class__.__name__.upper(),
            }

        return {
            'action': 'getResult',
            'winner': "Draw",
            'looser': "Draw",
            'cause': 'game-result-draw',
        }
