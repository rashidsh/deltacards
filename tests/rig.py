from dataclasses import dataclass
from typing import Sequence

from deltacards.model.enums import PlayerId
from deltacards.engine.game import Game
from deltacards.engine.runner import EngineUpdate, GameRunner
from deltacards.model.cards import Card, Monster, Spell
from deltacards.model.entity import Entity
from deltacards.model.player import Player
from deltacards.model.requests import Attack, ChoiceResponse, EndTurn, MulliganResponse, PendingChoiceRequest, \
    PendingMulliganRequest, PendingPlayerActionRequest, PlayMonster, PlaySpell, PlayerActionResponse
from deltacards.model.souls import Soul, soul

from .card_templates import load_test_templates


@soul('EMPTY')
class EmptySoul(Soul):
    """Soul with no effects to simplify testing"""
    pass


class RigError(Exception):
    pass


@dataclass
class RigConfig:
    soul_id: str = 'EMPTY'
    p1_artifacts: Sequence[int] = ()
    p2_artifacts: Sequence[int] = ()

    p1_deck: Sequence[int] = (1,)
    p2_deck: Sequence[int] = (1,)
    filler_id: int = 1

    starting_gold: int = 100
    auto_mulligan: bool = True


class RigPlayer:
    def __init__(self, rig: 'TestRig', player_id: PlayerId):
        self.rig = rig
        self.id = player_id

    @property
    def obj(self) -> Player:
        return self.rig.player(self.id)

    @property
    def opponent(self) -> 'RigPlayer':
        return self.rig.p2 if self.id is PlayerId.P1 else self.rig.p1

    @property
    def gold(self) -> int:
        return self.obj.gold

    @property
    def hp(self) -> int:
        return self.obj.hp

    @property
    def max_hp(self) -> int:
        return self.obj.max_hp

    @property
    def board(self) -> list[Monster | None]:
        return list(self.obj.board._cards)

    @property
    def hand(self) -> list[Card]:
        return list(self.obj.hand.cards)

    @property
    def deck(self) -> list[Card]:
        return list(self.obj.deck.cards)

    @property
    def dustpile(self) -> list[Card]:
        return list(self.obj.dustpile.cards)

    @property
    def erased(self) -> list[Card]:
        return list(self.obj.erased.cards)

    def require_action_request(self) -> PendingPlayerActionRequest:
        return self.rig._require_pending_request(PendingPlayerActionRequest, player_id=self.id)

    def require_choice_request(self) -> PendingChoiceRequest:
        return self.rig._require_pending_request(PendingChoiceRequest, player_id=self.id)

    def choose(self, options: list) -> EngineUpdate:
        req = self.require_choice_request()
        selected_ids = tuple(entity.id for entity in options)

        self.rig.send(
            ChoiceResponse(
                request_id=req.request_id,
                player_id=req.player_id,
                selected_option_ids=selected_ids,
            )
        )
        return self.rig.resolve_until_blocked()

    def play_monster(
        self,
        card: int | Monster,
        slot: int | None = None,
        target: Entity | None = None,
    ) -> EngineUpdate:
        req = self.require_action_request()

        if slot is None:
            try:
                slot = self.obj.board.get_empty_slot_index()
            except StopIteration as e:
                raise RigError("Board is full")

        if isinstance(card, int):
            card = self.obj.hand.get(card)

        assert isinstance(card, Monster), repr(card)

        self.rig.send(
            PlayerActionResponse(
                request_id=req.request_id,
                player_id=req.player_id,
                action=PlayMonster(card_id=card.id, board_slot=slot),
            )
        )

        upd = self.rig.resolve_until_blocked()

        if upd.pending and isinstance(upd.pending[0], PendingChoiceRequest) and upd.pending[0].player_id is self.id:
            if target is None:
                return upd

            self.choose([target])
            return self.rig.resolve_until_blocked()

        return upd

    def play_spell(
        self,
        card: int | Spell,
        target: Entity | None = None,
    ) -> EngineUpdate:
        req = self.require_action_request()

        if isinstance(card, int):
            card = self.obj.hand.get(card)

        assert isinstance(card, Spell), repr(card)

        self.rig.send(
            PlayerActionResponse(
                request_id=req.request_id,
                player_id=req.player_id,
                action=PlaySpell(card_id=card.id),
            )
        )

        upd = self.rig.resolve_until_blocked()

        if upd.pending and isinstance(upd.pending[0], PendingChoiceRequest) and upd.pending[0].player_id is self.id:
            if target is None:
                return upd

            self.choose([target])
            return self.rig.resolve_until_blocked()

        return upd

    def attack(
        self,
        attacker: Monster,
        defender: Monster | Player | RigPlayer,
    ) -> EngineUpdate:
        req = self.require_action_request()

        self.rig.send(
            PlayerActionResponse(
                request_id=req.request_id,
                player_id=req.player_id,
                action=Attack(attacker_id=attacker.id, defender_id=defender.id),
            )
        )
        return self.rig.resolve_until_blocked()

    def end_turn(self):
        req = self.require_action_request()
        self.rig.send(
            PlayerActionResponse(
                request_id=req.request_id,
                player_id=req.player_id,
                action=EndTurn(),
            )
        )
        return self.rig.resolve_until_blocked()


class TestRig:
    def __init__(self, game: Game, runner: GameRunner, config: RigConfig):
        self.game = game
        self.runner = runner
        self.config = config

        self.p1 = RigPlayer(self, PlayerId.P1)
        self.p2 = RigPlayer(self, PlayerId.P2)

    @classmethod
    def create(
        cls,
        soul_id: str = 'EMPTY',
        p1_artifacts: Sequence[int] = (),
        p2_artifacts: Sequence[int] = (),
        p1_deck: Sequence[int] = (1,),
        p2_deck: Sequence[int] = (1,),
        filler_id: int = 1,
        starting_gold: int = 100,
        auto_mulligan: bool = True,
    ) -> 'TestRig':
        load_test_templates()

        cfg = RigConfig(
            soul_id=soul_id,
            p1_artifacts=p1_artifacts,
            p2_artifacts=p2_artifacts,
            p1_deck=p1_deck,
            p2_deck=p2_deck,
            filler_id=filler_id,
            starting_gold=starting_gold,
            auto_mulligan=auto_mulligan,
        )

        p1_cards = cls._fill_deck(cfg.p1_deck, filler_id=cfg.filler_id)
        p2_cards = cls._fill_deck(cfg.p2_deck, filler_id=cfg.filler_id)

        p1 = Player(
            PlayerId.P1,
            deck=p1_cards,
            soul_id=cfg.soul_id,
            artifact_ids=cfg.p1_artifacts,
        )
        p2 = Player(
            PlayerId.P2,
            deck=p2_cards,
            soul_id=cfg.soul_id,
            artifact_ids=cfg.p2_artifacts,
        )

        p1.gold = cfg.starting_gold - 1  # first turn gives 1 gold
        p2.gold = cfg.starting_gold

        game = Game((p1, p2), seed=123)
        runner = GameRunner(game, no_initial_shuffle=True)

        rig = cls(game=game, runner=runner, config=cfg)
        rig.resolve_until_blocked()
        return rig

    @staticmethod
    def _fill_deck(ids: Sequence[int], filler_id: int) -> list[int]:
        res = list(ids)
        res.extend([filler_id] * (25 - len(res)))
        return res

    def _require_pending_request(self, type_, player_id: PlayerId | None = None):
        upd = self.resolve_until_blocked()
        pendings = []
        for req in upd.pending:
            if isinstance(req, type_) and ((player_id is None) or (req.player_id is player_id)):
                pendings.append(req)

        if len(pendings) != 1:
            raise RigError(
                f"Expected exactly 1 pending {type_.__name__} ({player_id=}), got {len(pendings)}: {pendings!r}"
            )

        return pendings[0]

    def send(self, response) -> None:
        ok, reason = self.runner.provide_input(response)
        if not ok:
            raise RigError(f"Runner rejected input {response!r}: {reason}")

    def resolve_until_blocked(self) -> EngineUpdate:
        """Resolve until blocked (pending request exists) or game ends."""
        while True:
            upd = self.runner.resolve_until_blocked()
            if upd.game_over:
                return upd

            if self.config.auto_mulligan:
                mulligans = [r for r in upd.pending if isinstance(r, PendingMulliganRequest)]
                if mulligans:
                    for req in mulligans:
                        self.send(
                            MulliganResponse(
                                request_id=req.request_id,
                                player_id=req.player_id,
                                replace_card_ids=(),
                            )
                        )
                    continue

            return upd

    @property
    def turn_player(self) -> RigPlayer:
        return self.p1 if self.game.turn_player.id is PlayerId.P1 else self.p2

    def player(self, player_id: PlayerId) -> Player:
        return self.game.player(player_id)

    def get_choices(self) -> list[Entity]:
        req = self.turn_player.require_choice_request()
        return req.prompt.options
