from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Callable, Iterable, Literal, TYPE_CHECKING

from deltacards.model.enums import DamageKind

if TYPE_CHECKING:
    from deltacards.engine.game import Game
    from deltacards.model.cards import Card, Monster
    from deltacards.model.entity import Entity


__all__ = (
    'CostQuery', 'StatQuery', 'DamageQuery', 'HealQuery',
    'ModKind',
    'CostLayer', 'StatLayer', 'DamageLayer', 'HealLayer',
    'ModifierQuery', 'ModifierLayer',
    'IntModifier',
    'RulesEngine',
)


@dataclass(frozen=True, slots=True)
class CostQuery:
    game: 'Game'
    card: 'Card'


@dataclass(frozen=True, slots=True)
class StatQuery:
    game: 'Game'
    monster: 'Monster'
    stat: Literal['attack', 'max_hp']


@dataclass(frozen=True, slots=True)
class DamageQuery:
    game: 'Game'
    source: 'Entity'
    target: 'Entity'
    amount: int
    kind: DamageKind

    combat_attacker: 'Monster | None' = None
    combat_defender: 'Entity | None' = None


@dataclass(frozen=True, slots=True)
class HealQuery:
    game: 'Game'
    source: 'Entity'
    target: 'Entity'
    amount: int


class ModKind(Enum):
    COST = 'cost'
    ATTACK = 'attack'
    MAX_HP = 'max_hp'
    DAMAGE = 'damage'
    HEAL = 'heal'


class CostLayer(IntEnum):
    ADD = 10
    SET = 20
    MIN = 30
    MAX = 40


class StatLayer(IntEnum):
    ADD = 10
    SET = 20
    MIN = 30
    MAX = 40


class DamageLayer(IntEnum):
    # "takes +1 / -2"
    ADD = 10
    # "can only take up to 3"
    CAP = 40
    # "can only be damaged by 4+"
    THRESHOLD = 50
    # "takes no damage"
    PREVENT = 60


class HealLayer(IntEnum):
    ADD = 10
    PREVENT = 60


ModifierQuery = CostQuery | StatQuery | DamageQuery | HealQuery
ModifierLayer = CostLayer | StatLayer | DamageLayer | HealLayer


@dataclass(frozen=True, slots=True)
class IntModifier:
    kind: ModKind
    layer: ModifierLayer
    source: 'Entity'
    description: str
    applies: Callable[[ModifierQuery], bool]
    apply: Callable[[int, ModifierQuery], int]

    unique: bool = False              # True for non-stacking modifiers
    key: str | None = None            # Must be set for non-stacking modifiers (uniqueness check)

    def __post_init__(self):
        if self.unique and not self.key:
            raise ValueError("unique=True requires key set")

    def sort_key(self) -> tuple[int, int, str]:
        return self.layer.value, self.source.id, self.description


class RulesEngine:
    def __init__(self, game: 'Game'):
        self.game = game

        self.revision = 1

        self._compiled_revision = 0
        self._rebuilding = False

        self._compiled_modifiers: dict[ModKind, list[IntModifier]] = {
            ModKind.COST: [],
            ModKind.ATTACK: [],
            ModKind.MAX_HP: [],
            ModKind.DAMAGE: [],
            ModKind.HEAL: [],
        }

    def invalidate(self) -> None:
        self.revision += 1
        self._compiled_revision = 0

    def iter_modifier_sources(self) -> Iterable['Entity']:
        for player in self.game.players.values():
            for card in player.board.cards:
                if not card.silenced:
                    yield card

            for enchantment in self.game.active_enchantments(player):
                yield enchantment

            for card in player.hand.cards:
                if not card.silenced:
                    yield card

            yield player.soul

            for artifact in player.artifacts:
                if artifact.active:
                    yield artifact

    def iter_modifiers(self) -> Iterable[IntModifier]:
        for src in self.iter_modifier_sources():
            yield from src.iter_modifiers(self.game)

    def _ensure_compiled(self) -> None:
        if self._compiled_revision == self.revision:
            # already up-to-date
            return

        if self._rebuilding:
            raise RuntimeError("Recursion detected while evaluating modifiers")

        self._rebuilding = True

        for kind in self._compiled_modifiers:
            self._compiled_modifiers[kind] = []

        for src in self.iter_modifier_sources():
            modifiers = src.iter_modifiers(self.game)
            if modifiers is not None:
                for mod in modifiers:
                    self._compiled_modifiers[mod.kind].append(mod)

        for mods in self._compiled_modifiers.values():
            mods.sort(key=lambda m: m.sort_key())

        self._compiled_revision = self.revision
        self._rebuilding = False

    def _apply_int_mods(
        self,
        *,
        base: int,
        kind: ModKind,
        query: ModifierQuery,
        clamp_min: int | None = None,
    ) -> int:
        self._ensure_compiled()

        modifiers = self._compiled_modifiers[kind]
        seen = set()
        value = base

        for mod in modifiers:
            if not mod.applies(query):
                continue

            if mod.unique:
                if mod.key in seen:
                    continue

                seen.add(mod.key)

            value = mod.apply(value, query)

        if clamp_min is not None:
            value = max(value, clamp_min)

        return value

    def cost(self, card: 'Card') -> int:
        base = card.base.cost + card.buffs.cost
        q = CostQuery(game=self.game, card=card)

        return self._apply_int_mods(
            base=base,
            kind=ModKind.COST,
            query=q,
            clamp_min=0,
        )

    def attack(self, monster: 'Monster') -> int:
        base = monster.base.attack + monster.buffs.attack
        q = StatQuery(game=self.game, monster=monster, stat='attack')

        return self._apply_int_mods(
            base=base,
            kind=ModKind.ATTACK,
            query=q,
            clamp_min=0,
        )

    def max_hp(self, monster: 'Monster') -> int:
        base = monster.base.hp + monster.buffs.max_hp
        q = StatQuery(game=self.game, monster=monster, stat='max_hp')

        return self._apply_int_mods(
            base=base,
            kind=ModKind.MAX_HP,
            query=q,
            clamp_min=0,
        )

    def damage(self, q: DamageQuery) -> int:
        return self._apply_int_mods(
            base=q.amount,
            kind=ModKind.DAMAGE,
            query=q,
            clamp_min=0,
        )

    def heal(self, q: HealQuery) -> int:
        return self._apply_int_mods(
            base=q.amount,
            kind=ModKind.HEAL,
            query=q,
            clamp_min=0,
        )
