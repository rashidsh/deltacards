from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from deltacards.content.library import LIBRARY
from deltacards.dsl.core import TargetSelector, TargetingError, Transform, ValueExpr, to_value
from deltacards.dsl.inspection import _MISSING, card_id_of, template_id_of
from deltacards.dsl.selectors import CARD_BY_NAME, SELF, YOU
from deltacards.dsl.values import TEMPLATE_ID
from deltacards.model.cards import Card, CardZone, Monster
from deltacards.model.entity import Entity
from deltacards.model.player import Player
from deltacards.model.snapshots import CardSnapshot
from deltacards.model.templates import CardTemplate

if TYPE_CHECKING:
    from deltacards.actions.standard import ActionContext


@dataclass(frozen=True, slots=True, eq=False)
class RandomTransform(Transform):
    """Get `n` random entities from a list"""
    n: ValueExpr

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        n = self.n.eval(ctx=ctx, **kwargs)
        if n <= 0 or not entities:
            return []

        items = entities.copy()
        ctx.game.rng.shuffle(items)

        return items[:n]

    def __repr__(self) -> str:
        return f"RANDOM({self.n!r})"


@dataclass(frozen=True, slots=True, eq=False)
class WeightedRandomTransform(Transform):
    weights: tuple[ValueExpr, ...]

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        if len(entities) != len(self.weights):
            raise TargetingError(
                f"WEIGHTED_RANDOM received {len(entities)} candidates "
                f"and {len(self.weights)} weights"
            )

        weighted_entities = []

        for entity, weight_expr in zip(entities, self.weights):
            weight = weight_expr.eval(ctx=ctx, entity=entity, **kwargs)
            if not isinstance(weight, int):
                raise TargetingError(
                    f"WEIGHTED_RANDOM weights must be integers, got "
                    f"{type(weight).__name__}"
                )

            if weight < 0:
                raise TargetingError(
                    "WEIGHTED_RANDOM weights must not be negative"
                )

            weighted_entities.extend([entity] * weight)

        if not weighted_entities:
            return []

        return [ctx.game.rng.choice(weighted_entities)]

    def __repr__(self) -> str:
        return f"WEIGHTED_RANDOM({', '.join(repr(weight) for weight in self.weights)})"


@dataclass(frozen=True, slots=True, eq=False)
class MinMaxTransform(Transform):
    mode: Literal['min', 'max']
    key: ValueExpr
    n: ValueExpr

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        n = self.n.eval(ctx=ctx, **kwargs)
        if n <= 0 or not entities:
            return []

        sorted_entities = sorted(
            entities,
            key=lambda e: self.key.eval(ctx=ctx, entity=e, **kwargs),
            reverse=(self.mode == 'max'),
        )
        return sorted_entities[:n]

    def __repr__(self) -> str:
        name = "MAX" if self.mode == 'max' else "MIN"
        return f"{name}({self.key!r}, n={self.n!r})"


@dataclass(frozen=True, slots=True, eq=False)
class LeftRightMostTransform(Transform):
    mode: Literal['left', 'right']

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        if not entities:
            return []

        for e in entities:
            if (not isinstance(e, Monster)) or (e.zone is not CardZone.BOARD):
                raise TargetingError(f"{self.mode.upper()}MOST expects monsters on board")

        reverse = (self.mode == 'right')
        return [sorted(entities, key=lambda m: m.pos, reverse=reverse)[0]]

    def __repr__(self) -> str:
        return "RIGHTMOST" if self.mode == 'right' else "LEFTMOST"


LEFTMOST = LeftRightMostTransform('left')
RIGHTMOST = LeftRightMostTransform('right')


@dataclass(frozen=True, slots=True, eq=False)
class DistinctTransform(Transform):
    key: ValueExpr

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        result = []
        seen = set()

        for entity in entities:
            key = self.key.eval(ctx=ctx, entity=entity, **kwargs)
            if key in seen:
                continue

            seen.add(key)
            result.append(entity)

        return result

    def __repr__(self) -> str:
        return f"DISTINCT({self.key!r})"


@dataclass(frozen=True, slots=True, eq=False)
class SortByTransform(Transform):
    key: ValueExpr
    reverse: bool = False

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        return sorted(
            entities,
            key=lambda entity: self.key.eval(ctx=ctx, entity=entity, **kwargs),
            reverse=bool(self.reverse),
        )

    def __repr__(self) -> str:
        return f"SORT_BY({self.key!r}, reverse={self.reverse})"


@dataclass(frozen=True, slots=True, eq=False)
class GenerateCardsTransform(Transform):
    controller: TargetSelector
    creator: TargetSelector | None
    count: ValueExpr

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        controller = self.controller.eval_optional_one(ctx=ctx, **kwargs)
        if controller is None:
            return []

        if not isinstance(controller, Player):
            raise TargetingError(f"GENERATE_CARD() controller must be a player, got {type(controller).__name__}")

        creator_id = None
        creator_base_identity = None

        if self.creator is not None:
            creator = self.creator.eval_optional_one(ctx=ctx, **kwargs)
            if creator is not None:
                creator_base_identity = creator.base_identity
                if isinstance(creator, Entity):
                    creator_id = creator.id

        count = self.count.eval(ctx=ctx, **kwargs)
        if count <= 0:
            return []

        assert all(isinstance(e, CardTemplate) for e in entities)
        template_ids = tuple(template.id for template in entities)

        result = []
        for template_id in template_ids:
            for _ in range(count):
                result.append(
                    ctx.game.create_card(
                        template_id=template_id,
                        controller_id=controller.id,
                        creator_id=creator_id,
                        creator_base_identity=creator_base_identity,
                    )
                )

        return result

    def __repr__(self) -> str:
        return (
            f"GenerateCardsTransform("
            f"controller={self.controller!r}, "
            f"creator={self.creator!r}, "
            f"count={self.count!r})"
        )


@dataclass(frozen=True, slots=True, eq=False)
class CopyTransform(Transform):
    exact: bool
    controller: TargetSelector
    creator: TargetSelector | None = None

    def _resolve_creator(self, ctx: 'ActionContext', **kwargs) -> Entity | None:
        if self.creator is None:
            if isinstance(ctx.source, Entity):
                return ctx.source
            else:
                raise TargetingError(f"COPY(): unable to identify copy source from `ctx.source`")

        creator = self.creator.eval_optional_one(ctx=ctx, **kwargs)
        if creator is None:
            raise TargetingError(f"COPY(): unable to identify copy source from `creator`")

        if not isinstance(creator, Entity):
            raise TargetingError(f"COPY() creator must be an entity, got {type(creator).__name__}")

        return creator

    def apply(self, entities: list[Any], ctx: 'ActionContext', **kwargs) -> list[Any]:
        if not entities:
            return []

        controller = self.controller.eval_optional_one(ctx=ctx, **kwargs)
        if controller is None:
            return []

        creator = self._resolve_creator(ctx, **kwargs)

        result = []
        for card in entities:
            if self.exact:
                if not isinstance(card, Card):
                    raise TargetingError(f"EXACT_COPY expects runtime Cards, got {type(card).__name__}")

                result.append(
                    ctx.game.create_card_copy_exact(
                        card,
                        controller_id=controller.id,
                        creator_id=creator.id,
                        creator_base_identity=creator.base_identity,
                    )
                )
            else:
                if not isinstance(card, (Card, CardSnapshot)):
                    raise TargetingError(f"COPY expects Cards or CardSnapshots, got {type(card).__name__}")

                result.append(
                    ctx.game.create_card_copy(
                        card,
                        controller_id=controller.id,
                        creator_id=creator.id,
                        creator_base_identity=creator.base_identity,
                    )
                )

        return result

    def __repr__(self) -> str:
        name = "EXACT_COPY" if self.exact else "COPY"
        args = []

        if self.controller is not YOU:
            args.append(f"controller={self.controller!r}")
        if self.creator is not None:
            args.append(f"creator={self.creator!r}")

        return f"{name}({', '.join(args)})"


def RANDOM(n: int | ValueExpr = 1) -> RandomTransform:
    return RandomTransform(to_value(n))


def WEIGHTED_RANDOM(*weights: int | ValueExpr) -> WeightedRandomTransform:
    return WeightedRandomTransform(
        weights=tuple(to_value(weight) for weight in weights),
    )


def MIN(key: ValueExpr, n: int | ValueExpr = 1) -> MinMaxTransform:
    return MinMaxTransform('min', key=key, n=to_value(n))


def MAX(key: ValueExpr, n: int | ValueExpr = 1) -> MinMaxTransform:
    return MinMaxTransform('max', key=key, n=to_value(n))


def DISTINCT(key: ValueExpr | None = None) -> DistinctTransform:
    return DistinctTransform(key=TEMPLATE_ID if key is None else key)


def SORT_BY(key: ValueExpr, reverse: bool = False) -> SortByTransform:
    return SortByTransform(key=key, reverse=reverse)


def GENERATE_CARD(
    spec = None,
    *,
    controller: TargetSelector | None = None,
    creator: TargetSelector | None = None,
    count: int | ValueExpr = 1,
):
    transform = GenerateCardsTransform(
        controller=YOU if controller is None else controller,
        creator=SELF if creator is None else creator,
        count=to_value(count),
    )

    if spec is None:
        return transform

    if isinstance(spec, str):
        return CARD_BY_NAME(spec) >> transform

    return spec >> transform


def COPY(
    controller: TargetSelector | None = None,
    creator: TargetSelector | None = None,
) -> CopyTransform:
    return CopyTransform(
        exact=False,
        controller=YOU if controller is None else controller,
        creator=SELF if creator is None else creator,
    )


def EXACT_COPY(
    controller: TargetSelector | None = None,
    creator: TargetSelector | None = None,
) -> CopyTransform:
    return CopyTransform(
        exact=True,
        controller=YOU if controller is None else controller,
        creator=SELF if creator is None else creator,
    )


@dataclass(frozen=True, slots=True, eq=False)
class AsTemplatesTransform(Transform):
    distinct: bool = False

    def apply(self, entities: list[Any], *, ctx: 'ActionContext', **kwargs) -> list[Any]:
        result = []
        seen_template_ids = set()

        for entity in entities:
            template_id = template_id_of(entity, default=_MISSING)
            if template_id is _MISSING:
                raise TargetingError(f"AS_TEMPLATES expects card-like objects, got {entity!r}")

            if self.distinct:
                if template_id in seen_template_ids:
                    continue

                seen_template_ids.add(template_id)

            result.append(LIBRARY.get(template_id))

        return result

    def __repr__(self) -> str:
        return f"AS_TEMPLATES(distinct={self.distinct})"


def AS_TEMPLATES(distinct: bool = False) -> AsTemplatesTransform:
    return AsTemplatesTransform(distinct=distinct)


@dataclass(frozen=True, slots=True, eq=False)
class AsCardsTransform(Transform):
    def apply(self, entities: list[Any], *, ctx: 'ActionContext', **kwargs) -> list[Any]:
        result = []

        for entity in entities:
            card_id = card_id_of(entity, default=_MISSING)
            if card_id is _MISSING:
                raise TargetingError(f"AS_CARDS expects card-like objects, got {entity!r}")

            result.append(ctx.game.entity(card_id))

        return result

    def __repr__(self) -> str:
        return "AS_CARDS()"


AS_CARDS = AsCardsTransform


@dataclass(frozen=True, slots=True, eq=False)
class LimitPerTransform(Transform):
    key: ValueExpr
    n: ValueExpr

    def apply(self, entities: list[Any], *, ctx: 'ActionContext', **kwargs) -> list[Any]:
        n = self.n.eval(ctx=ctx, **kwargs)
        if n <= 0:
            return []

        result = []
        counts = {}

        for entity in entities:
            key = self.key.eval(ctx=ctx, entity=entity, **kwargs)

            count = counts.get(key, 0)
            if count >= n:
                continue

            counts[key] = count + 1
            result.append(entity)

        return result

    def __repr__(self) -> str:
        return f"LIMIT_PER({self.key!r}, {self.n!r})"


def LIMIT_PER(key: Any, n: int | ValueExpr) -> LimitPerTransform:
    return LimitPerTransform(key=to_value(key), n=to_value(n))
