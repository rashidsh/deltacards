from dataclasses import dataclass
from typing import Any, ClassVar, Literal, TYPE_CHECKING

from deltacards.content.library import LIBRARY
from deltacards.dsl.core import TargetSelector, TargetingError, ValueExpr, resolve_selector_value, to_value
from deltacards.model.artifacts import ARTIFACTS
from deltacards.model.cards import Card, CardZone, Monster
from deltacards.model.enchantments import ENCHANTMENTS, Enchantment
from deltacards.model.slots import BoardSlot
from deltacards.model.snapshots import MonsterSnapshot
from deltacards.model.templates import CardTemplate

if TYPE_CHECKING:
    from deltacards.actions.standard import ActionContext


# --------------------
# Context selectors
# --------------------

@dataclass(frozen=True, slots=True, eq=False)
class SelfSelector(TargetSelector):
    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        return [ctx.source]

    def __repr__(self) -> str:
        return "SELF"


@dataclass(frozen=True, slots=True, eq=False)
class EnvSelector(TargetSelector):
    key: str

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        try:
            value = ctx.env[self.key]
        except KeyError:
            raise TargetingError(f"ctx.env['{self.key}'] is not set")

        return resolve_selector_value(value, ctx=ctx, **kwargs)

    def __repr__(self) -> str:
        return self.key.upper()


@dataclass(frozen=True, slots=True, eq=False)
class YouSelector(TargetSelector):
    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        player_id = ctx.source.controller_id
        return [ctx.game.player(player_id)]

    def __repr__(self) -> str:
        return "YOU"


@dataclass(frozen=True, slots=True, eq=False)
class OpponentSelector(TargetSelector):
    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        player_id = ctx.source.controller_id
        return [ctx.game.player(player_id).opponent]

    def __repr__(self) -> str:
        return "OPPONENT"


@dataclass(frozen=True, slots=True, eq=False)
class TurnPlayerSelector(TargetSelector):
    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        return [ctx.game.turn_player]

    def __repr__(self) -> str:
        return "TURN_PLAYER"


# --------------------------
# Type conversion selectors
# --------------------------

@dataclass(frozen=True, slots=True, eq=False)
class ResolveEntitySelector(TargetSelector):
    entity_id: ValueExpr

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        entity_id = self.entity_id.eval(ctx=ctx, **kwargs)
        return [ctx.game.entity(entity_id)]

    def __repr__(self) -> str:
        return f"RESOLVE_ENTITY({self.entity_id!r})"


def RESOLVE_ENTITY(entity_id: Any) -> ResolveEntitySelector:
    return ResolveEntitySelector(to_value(entity_id))


# --------------------
# Range generators
# --------------------

@dataclass(frozen=True, slots=True, eq=False)
class RangeSelector(TargetSelector):
    start: ValueExpr
    stop: ValueExpr
    step: ValueExpr

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        start = self.start.eval(ctx=ctx, **kwargs)
        stop = self.stop.eval(ctx=ctx, **kwargs)
        step = self.step.eval(ctx=ctx, **kwargs)

        return list(range(start, stop, step))

    def __repr__(self) -> str:
        return f"RANGE({self.start!r}, {self.stop!r}, {self.step!r})"


def RANGE(start: Any, stop: Any, step: Any = 1) -> RangeSelector:
    return RangeSelector(to_value(start), to_value(stop), to_value(step))


# ------------------------
# Entity player selectors
# ------------------------

@dataclass(frozen=True, slots=True, eq=False)
class EntityControllerSelector(TargetSelector):
    inner: TargetSelector

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        entity = self.inner.eval_optional_one(ctx=ctx, **kwargs)
        if entity is None:
            return []

        player_id = entity.controller_id
        return [ctx.game.player(player_id)]

    def __repr__(self) -> str:
        return f"CONTROLLER_OF({self.inner!r})"


@dataclass(frozen=True, slots=True, eq=False)
class EntityOpponentSelector(TargetSelector):
    inner: TargetSelector

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        player = CONTROLLER_OF(self.inner).eval_optional_one(ctx=ctx, **kwargs)
        if player is None:
            return []

        return [player.opponent]

    def __repr__(self) -> str:
        return f"OPPONENT_OF({self.inner!r})"


def CONTROLLER_OF(x: TargetSelector) -> EntityControllerSelector:
    return EntityControllerSelector(x)


def OPPONENT_OF(x: TargetSelector) -> EntityOpponentSelector:
    return EntityOpponentSelector(x)


# --------------------
# Zone selectors
# --------------------

@dataclass(frozen=True, slots=True, eq=False)
class ZoneSelector(TargetSelector):
    zone: CardZone
    player: TargetSelector

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        player = self.player.eval_optional_one(ctx=ctx, **kwargs)
        if player is None:
            return []

        container = getattr(player, self.zone.value)
        return container.cards.copy()

    def __repr__(self) -> str:
        return f"{self.zone.value.upper()}({self.player!r})"


def BOARD_OF(player: TargetSelector) -> ZoneSelector:
    return ZoneSelector(CardZone.BOARD, player)


def HAND_OF(player: TargetSelector) -> ZoneSelector:
    return ZoneSelector(CardZone.HAND, player)


def DECK_OF(player: TargetSelector) -> ZoneSelector:
    return ZoneSelector(CardZone.DECK, player)


def DUSTPILE_OF(player: TargetSelector) -> ZoneSelector:
    return ZoneSelector(CardZone.DUSTPILE, player)


def ERASED_OF(player: TargetSelector) -> ZoneSelector:
    return ZoneSelector(CardZone.ERASED, player)


# -------------------------
# Board-relative selectors
# -------------------------

@dataclass(frozen=True, slots=True, eq=False)
class RelativeBoardSelector(TargetSelector):
    inner: TargetSelector
    offset: int
    opponent_side: bool = False

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        monster = self.inner.eval_optional_one(ctx=ctx, **kwargs)
        if monster is None:
            return []

        if not isinstance(monster, (Monster, MonsterSnapshot)):
            raise TargetingError(f"RelativeBoardSelector expects Monster/MonsterSnapshot, got {type(monster).__name__}: {monster!r}")

        if isinstance(monster, Monster) and monster.zone is not CardZone.BOARD:
            return []

        player = ctx.game.player(monster.controller_id)
        if self.opponent_side:
            player = player.opponent

        pos = monster.pos + self.offset
        if not (0 <= pos < player.board.MAX_CARDS):
            return []

        monster = player.board[pos]
        return [monster] if monster is not None else []

    def __repr__(self) -> str:
        if self.opponent_side and self.offset == 0:
            return f"FRONT({self.inner!r})"

        if self.offset == -1:
            return f"LEFT({self.inner!r})"

        if self.offset == +1:
            return f"RIGHT({self.inner!r})"

        return f"RelativeBoardSelector({self.inner!r}, offset={self.offset}, opponent_side={self.opponent_side})"


def LEFT(x: TargetSelector) -> RelativeBoardSelector:
    return RelativeBoardSelector(x, offset=-1, opponent_side=False)


def RIGHT(x: TargetSelector) -> RelativeBoardSelector:
    return RelativeBoardSelector(x, offset=+1, opponent_side=False)


def ADJACENT(x: TargetSelector) -> TargetSelector:
    return LEFT(x) | RIGHT(x)


def FRONT(x: TargetSelector) -> RelativeBoardSelector:
    return RelativeBoardSelector(x, offset=0, opponent_side=True)


@dataclass(frozen=True, slots=True, eq=False)
class RelativeBoardRangeSelector(TargetSelector):
    inner: TargetSelector
    direction: Literal['left', 'right']

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        monster = self.inner.eval_optional_one(ctx=ctx, **kwargs)
        if monster is None:
            return []

        if not isinstance(monster, (Monster, MonsterSnapshot)):
            raise TargetingError(f"RelativeBoardRangeSelector expects Monster/MonsterSnapshot, got {type(monster).__name__}: {monster!r}")

        if monster.zone is not CardZone.BOARD:
            return []

        player = ctx.game.player(monster.controller_id)

        if self.direction == 'left':
            slots = range(0, monster.pos)
        else:
            slots = range(monster.pos + 1, player.board.MAX_CARDS)

        result = []
        for index in slots:
            m = player.board[index]
            if m is not None:
                result.append(m)

        return result

    def __repr__(self) -> str:
        return f"{'LEFT_OF' if self.direction == 'left' else 'RIGHT_OF'}({self.inner!r})"


def LEFT_OF(x: TargetSelector) -> RelativeBoardRangeSelector:
    return RelativeBoardRangeSelector(x, direction='left')


def RIGHT_OF(x: TargetSelector) -> RelativeBoardRangeSelector:
    return RelativeBoardRangeSelector(x, direction='right')


# ------------------------
# Hand-relative selectors
# ------------------------

@dataclass(frozen=True, slots=True, eq=False)
class RelativeHandSelector(TargetSelector):
    inner: TargetSelector
    offset: int

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        card = self.inner.eval_optional_one(ctx=ctx, **kwargs)
        if card is None:
            return []

        if not isinstance(card, Card):
            raise TargetingError(f"RelativeHandSelector expects Card, got {type(card).__name__}: {card!r}")

        player = ctx.game.player(card.controller_id)
        cards = player.hand.cards

        try:
            index = cards.index(card)
        except ValueError:
            return []

        target_index = index + self.offset
        if 0 <= target_index < len(cards):
            return [cards[target_index]]

        return []

    def __repr__(self) -> str:
        if self.offset == -1:
            return f"LEFT_IN_HAND({self.inner!r})"
        if self.offset == +1:
            return f"RIGHT_IN_HAND({self.inner!r})"

        return f"RelativeHandSelector({self.inner!r}, offset={self.offset})"


def LEFT_IN_HAND(x: TargetSelector) -> RelativeHandSelector:
    return RelativeHandSelector(x, offset=-1)


def RIGHT_IN_HAND(x: TargetSelector) -> RelativeHandSelector:
    return RelativeHandSelector(x, offset=+1)


def ADJACENT_IN_HAND(x: TargetSelector) -> TargetSelector:
    return LEFT_IN_HAND(x) | RIGHT_IN_HAND(x)


@dataclass(frozen=True, slots=True, eq=False)
class RelativeHandRangeSelector(TargetSelector):
    inner: TargetSelector
    direction: Literal['left', 'right']

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        card = self.inner.eval_optional_one(ctx=ctx, **kwargs)
        if card is None:
            return []

        if not isinstance(card, Card):
            raise TargetingError(f"RelativeHandRangeSelector expects Card, got {type(card).__name__}: {card!r}")

        player = ctx.game.player(card.controller_id)
        cards = player.hand.cards

        try:
            index = cards.index(card)
        except ValueError:
            return []

        if self.direction == 'left':
            return cards[:index]

        return cards[index + 1:]

    def __repr__(self) -> str:
        return f"{'LEFT_OF_HAND' if self.direction == 'left' else 'RIGHT_OF_HAND'}({self.inner!r})"


def LEFT_OF_HAND(x: TargetSelector) -> RelativeHandRangeSelector:
    return RelativeHandRangeSelector(x, direction='left')


def RIGHT_OF_HAND(x: TargetSelector) -> RelativeHandRangeSelector:
    return RelativeHandRangeSelector(x, direction='right')


# --------------------
# Library selectors
# --------------------

@dataclass(frozen=True, slots=True, eq=False)
class CardLibrarySelector(TargetSelector):
    _cards_cache: ClassVar[list[CardTemplate] | None] = None

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        cards = CardLibrarySelector._cards_cache
        if cards is None:
            cards = sorted(
                LIBRARY._by_id.values(),
                key=lambda card: (card.cost, card.id),
            )
            CardLibrarySelector._cards_cache = cards

        return cards

    def __repr__(self) -> str:
        return "CARD_LIBRARY"


@dataclass(frozen=True, slots=True, eq=False)
class CardByNameSelector(TargetSelector):
    name: str

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        return [LIBRARY.get_by_name(self.name)]

    def __repr__(self) -> str:
        return f"CARD_BY_NAME({self.name!r})"


def CARD_BY_NAME(name: str) -> CardByNameSelector:
    return CardByNameSelector(name=name)


# --------------------
# Artifact selectors
# --------------------

@dataclass(frozen=True, slots=True, eq=False)
class ArtifactByNameSelector(TargetSelector):
    name: str

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        return [artifact for artifact in ARTIFACTS.values() if artifact.name == self.name]

    def __repr__(self) -> str:
        return f"ARTIFACT_BY_NAME({self.name!r})"


def ARTIFACT_BY_NAME(name: str) -> ArtifactByNameSelector:
    return ArtifactByNameSelector(name=name)


@dataclass(frozen=True, slots=True, eq=False)
class PlayerArtifactSelector(TargetSelector):
    player: TargetSelector
    name: str

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        player = self.player.eval_optional_one(ctx=ctx, **kwargs)
        if player is None:
            return []

        return [artifact for artifact in player.artifacts if artifact.name == self.name]

    def __repr__(self) -> str:
        return f"ARTIFACT_OF_PLAYER({self.player!r}, name={self.name})"


def ARTIFACT_OF_PLAYER(player: TargetSelector, name: str) -> PlayerArtifactSelector:
    return PlayerArtifactSelector(player=player, name=name)


# ---------------------
# Board slot selectors
# ---------------------

@dataclass(frozen=True, slots=True, eq=False)
class PlayerBoardSlotsSelector(TargetSelector):
    player: Any

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        player = self.player.eval_optional_one(ctx=ctx, **kwargs)
        if player is None:
            return []

        return player.board_slots.copy()

    def __repr__(self) -> str:
        return f"BOARD_SLOTS_OF({self.player!r})"


def BOARD_SLOTS_OF(player: Any) -> PlayerBoardSlotsSelector:
    return PlayerBoardSlotsSelector(player)


@dataclass(frozen=True, slots=True, eq=False)
class SlotOfSelector(TargetSelector):
    inner: TargetSelector

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        values = self.inner.eval(ctx=ctx, **kwargs)

        result = []
        seen_ids = set()

        for value in values:
            if isinstance(value, BoardSlot):
                slot = value

            elif isinstance(value, Monster):
                if value.zone is CardZone.BOARD:
                    slot = ctx.game.board_slot(value.controller_id, value.pos)
                else:
                    slot = None

            elif isinstance(value, Enchantment):
                slot = ctx.game.entity(value.slot_id)

            else:
                raise TypeError(
                    f"SLOT_OF expects BoardSlot/Monster/Enchantment; "
                    f"got {type(value).__name__}"
                )

            if (slot is None) or (slot.id in seen_ids):
                continue

            seen_ids.add(slot.id)
            result.append(slot)

        return result

    def __repr__(self) -> str:
        return f"SLOT_OF({self.target!r})"


def SLOT_OF(target: Any) -> SlotOfSelector:
    return SlotOfSelector(target)


@dataclass(frozen=True, slots=True, eq=False)
class MonsterInSlotSelector(TargetSelector):
    slots: Any

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        values = self.slots.eval(ctx=ctx, **kwargs)

        result = []

        for value in values:
            if not isinstance(value, BoardSlot):
                raise TypeError(
                    f"MONSTER_IN_SLOT expects BoardSlot, "
                    f"got {type(value).__name__}"
                )

            if value.monster_id is None:
                continue

            entity = ctx.game.entity(value.monster_id)
            if entity.zone is not CardZone.BOARD:
                continue

            result.append(entity)

        return result

    def __repr__(self) -> str:
        return f"MONSTER_IN_SLOT({self.slots!r})"


def MONSTER_IN_SLOT(slots: Any) -> MonsterInSlotSelector:
    return MonsterInSlotSelector(slots)


# ----------------------
# Enchantment selectors
# ----------------------

@dataclass(frozen=True, slots=True, eq=False)
class EnchantmentByNameSelector(TargetSelector):
    name: str

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        return [enchantment for name, enchantment in ENCHANTMENTS.items() if name == self.name]

    def __repr__(self) -> str:
        return f"ENCHANTMENT_BY_NAME({self.name!r})"


def ENCHANTMENT_BY_NAME(name: str) -> EnchantmentByNameSelector:
    return EnchantmentByNameSelector(name=name)


@dataclass(frozen=True, slots=True, eq=False)
class PlayerEnchantmentsSelector(TargetSelector):
    player: Any

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        player = self.player.eval_optional_one(ctx=ctx, **kwargs)
        if player is None:
            return []

        return ctx.game.active_enchantments(player)

    def __repr__(self) -> str:
        return f"ENCHANTMENTS_OF({self.player!r})"


def ENCHANTMENTS_OF(player: Any) -> PlayerEnchantmentsSelector:
    return PlayerEnchantmentsSelector(player)


@dataclass(frozen=True, slots=True, eq=False)
class EnchantmentInSlotSelector(TargetSelector):
    slots: Any

    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        values = self.slots.eval(ctx=ctx, **kwargs)

        result = []

        for value in values:
            if not isinstance(value, BoardSlot):
                raise TypeError(
                    f"ENCHANTMENT_IN_SLOT expects BoardSlot, "
                    f"got {type(value).__name__}"
                )

            enchantment = ctx.game.enchantment_on_slot(value)
            if enchantment is not None:
                result.append(enchantment)

        return result

    def __repr__(self) -> str:
        return f"ENCHANTMENT_IN_SLOT({self.slots!r})"


def ENCHANTMENT_IN_SLOT(
    slots: Any,
) -> EnchantmentInSlotSelector:
    return EnchantmentInSlotSelector(slots)


# ---------------------
# Selectors for macros
# ---------------------

@dataclass(frozen=True, slots=True, eq=False)
class NextLostSoulSelector(TargetSelector):
    def eval(self, ctx: 'ActionContext', **kwargs) -> list[Any]:
        lost_soul_card_names = ("Lost Alphys", "Lost Papyrus", "Lost Undyne", "Lost Toriel", "Lost Asgore", "Lost Sans")
        player_id = ctx.source.controller_id
        player = ctx.game.player(player_id)

        if player.next_lost_soul is not None:
            card = LIBRARY.get_by_name(lost_soul_card_names[player.next_lost_soul])
            player.next_lost_soul += 1
            if player.next_lost_soul >= len(lost_soul_card_names):
                player.next_lost_soul = 0

        else:
            card = LIBRARY.get_by_name(ctx.game.rng.choice(lost_soul_card_names))

        return [card]

    def __repr__(self) -> str:
        return "NEXT_LOST_SOUL"


SELF = SelfSelector()
TARGET = EnvSelector('target')
KILLER = EnvSelector('killer')
ATTACKER = EnvSelector('attacker')
DEFENDER = EnvSelector('defender')
LOOP_COPY = EnvSelector('loop_copy')
TRIGGER_CARD = EnvSelector('trigger_card')
DEATH_SLOT = EnvSelector('death_slot')

YOU = YouSelector()
CONTROLLER = YOU
OPPONENT = OpponentSelector()
TURN_PLAYER = TurnPlayerSelector()
ALL_PLAYERS = YOU | OPPONENT

BOARD = ZoneSelector(CardZone.BOARD, YOU)
HAND = ZoneSelector(CardZone.HAND, YOU)
DECK = ZoneSelector(CardZone.DECK, YOU)
DUSTPILE = ZoneSelector(CardZone.DUSTPILE, YOU)
ERASED = ZoneSelector(CardZone.ERASED, YOU)

OPPONENT_BOARD = ZoneSelector(CardZone.BOARD, OPPONENT)
OPPONENT_HAND = ZoneSelector(CardZone.HAND, OPPONENT)
OPPONENT_DECK = ZoneSelector(CardZone.DECK, OPPONENT)
OPPONENT_DUSTPILE = ZoneSelector(CardZone.DUSTPILE, OPPONENT)
OPPONENT_ERASED = ZoneSelector(CardZone.ERASED, OPPONENT)

ALLY_MONSTERS = BOARD
ENEMY_MONSTERS = OPPONENT_BOARD
ALL_MONSTERS = ALLY_MONSTERS | ENEMY_MONSTERS

ALLIES = YOU | ALLY_MONSTERS
ENEMIES = OPPONENT | ENEMY_MONSTERS

CARD_LIBRARY = CardLibrarySelector()

ALLY_SLOTS = BOARD_SLOTS_OF(YOU)
ENEMY_SLOTS = BOARD_SLOTS_OF(OPPONENT)
ALL_SLOTS = ALLY_SLOTS | ENEMY_SLOTS

THIS_SLOT_MONSTER = MONSTER_IN_SLOT(SLOT_OF(SELF))

ALLY_ENCHANTMENTS = ENCHANTMENTS_OF(YOU)
ENEMY_ENCHANTMENTS = ENCHANTMENTS_OF(OPPONENT)
ALL_ENCHANTMENTS = ALLY_ENCHANTMENTS | ENEMY_ENCHANTMENTS
