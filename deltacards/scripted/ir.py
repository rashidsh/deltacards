import re
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any

from deltacards.actions.base import Action
from deltacards.actions.results import (
    ActionResult,
    AbilityTriggeredResult,
    AttackDeclaredResult,
    AttackResolvedResult,
    BoardSlotEnchantedResult,
    CardDrawnResult,
    CardOverdrawnResult,
    CardPlayedResult,
    CardRevealedResult,
    DodgeConsumedResult,
    EnchantmentRemovedResult,
    EntityDamagedResult,
    EntityHealedResult,
    GoldSpentResult,
    MonsterKilledResult,
    MonsterSummonedResult,
    SpellCastResult,
)
from deltacards.actions.standard import (
    AddArtifact,
    AddKeyword,
    Attack,
    Buff,
    Cast,
    Catch,
    Choose,
    Draw,
    DrawNext,
    EarnGold,
    Enchant,
    Erase,
    Heal,
    HalveStats,
    Hit,
    Kill,
    Move,
    Paralyze,
    RefreshAttacks,
    ReleaseCaughtCard,
    RemoveEnchantment,
    RemoveKeyword,
    RemoveNegativeEffects,
    RemoveStatus,
    Reveal,
    ScheduleEffect,
    SetBaseStats,
    SetGold,
    SetPlayerHP,
    SetStats,
    SetStatus,
    SetVar,
    Silence,
    SkipNextTurn,
    SpendGold,
    Summon,
    SwapCards,
    SwapStats,
    TakeFatigueDamage,
    ToggleAbility,
    ToggleArtifact,
    TransformArtifact,
    TransformCard,
    TransformEnchantment,
    TriggerAbility,
    UpdateArtifactCounter,
    UpdateEnchantmentCounter,
)
from deltacards.content.catalog import ContentCatalog
from deltacards.content.library import normalize_content_name
from deltacards.dsl.aggregates import (
    COUNT,
    COUNT_DISTINCT,
    COUNT_UNIQUE_TRIBES,
    EXISTS,
    MAXVAL,
    MINVAL,
    SUM,
    UNIQUE_TRIBES,
    UNIQUE_VALUES,
)
from deltacards.dsl.core import (
    BooleanValue,
    Predicate,
    PredicateAsValueExpr,
    TargetSelector,
    ValueExpr,
    to_value,
)
from deltacards.dsl.discovery import DISCOVER
from deltacards.dsl.events import EVENT
from deltacards.dsl.history import PLAYER_SOUL
from deltacards.dsl.macros import (
    DrawUpTo,
    FillBoard,
    FillHand,
    NEXT_LOST_SOUL,
    Program,
    Switch,
)
from deltacards.dsl.predicates import (
    DAMAGED,
    DEAD,
    EMPTY_SLOT,
    ENCHANTED_SLOT,
    EXPANSION,
    GENERATED,
    GENERATED_BY,
    HAS_ABILITY,
    HAS_ANY_TRIBE,
    HAS_NEGATIVE_EFFECTS,
    HAS_KEYWORD,
    HAS_STATUS,
    HAS_TRIBE,
    IS_MONSTER,
    IS_SPELL,
    NON_GENERATED,
    OCCUPIED_SLOT,
    SLOT_HAS_ENCHANTMENT,
    UNENCHANTED_SLOT,
)
from deltacards.dsl.selectors import (
    ADJACENT,
    ADJACENT_IN_HAND,
    ALLIES,
    ALL_ENCHANTMENTS,
    ALL_MONSTERS,
    ALL_PLAYERS,
    ALL_SLOTS,
    ALLY_MONSTERS,
    ALLY_SLOTS,
    ARTIFACT_BY_NAME,
    ARTIFACT_OF_PLAYER,
    ATTACKER,
    BOARD_OF,
    BOARD_SLOTS_OF,
    CARD_BY_NAME,
    CARD_LIBRARY,
    CONTROLLER_OF,
    DEATH_SLOT,
    DECK,
    DECK_OF,
    DEFENDER,
    DUSTPILE_OF,
    ENCHANTMENTS_OF,
    ENCHANTMENT_BY_NAME,
    ENCHANTMENT_IN_SLOT,
    ENEMIES,
    ENEMY_MONSTERS,
    ENEMY_SLOTS,
    ERASED_OF,
    FRONT,
    HAND,
    HAND_OF,
    KILLER,
    LEFT,
    LEFT_IN_HAND,
    LEFT_OF,
    LEFT_OF_HAND,
    LOOP_COPY,
    MONSTER_IN_SLOT,
    OPPONENT,
    OPPONENT_OF,
    RESOLVE_ENTITY,
    RIGHT,
    RIGHT_IN_HAND,
    RIGHT_OF,
    RIGHT_OF_HAND,
    SELF,
    SLOT_OF,
    TARGET,
    THIS_SLOT_MONSTER,
    TRIGGER_CARD,
    TURN_PLAYER,
    YOU,
)
from deltacards.dsl.transforms import (
    COPY,
    DISTINCT,
    EXACT_COPY,
    GENERATE_CARD,
    LEFTMOST,
    LIMIT_PER,
    MAX,
    MIN,
    RANDOM,
    RIGHTMOST,
    SORT_BY,
)
from deltacards.dsl.values import (
    ATTACK,
    CLAMP,
    COST,
    CREATOR_ID,
    EMPTY_SLOTS,
    GREATEST,
    HAS_ARTIFACT,
    HP,
    ID,
    LEAST,
    RARITY,
    SYNERGY_TRIGGERED,
    TEMPLATE_ID,
    AttrValue,
    SelectorAttrValue,
)
from deltacards.dsl.vars import (
    CHOICE_NOT_SELECTED,
    CHOICE_SELECTED,
    SelectorVar,
    ValueVar,
    Var,
)
from deltacards.engine.effects import Check, For, ForEach, NoEffect, StepResult
from deltacards.model.artifacts import ArtifactRarity
from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardToggleableAbility,
    CardZone,
    DamageKind,
    Expansion,
    KillCause,
    Tribe,
)
from deltacards.scripted.runtime import CompiledProgram, CompiledReaction
from deltacards.scripted.validation import ParsedEntity, ValidationContext


_ALLOWED_ABILITIES = {
    'monster': frozenset({
        Ability.MAGIC,
        Ability.SYNERGY,
        Ability.DUST,
        Ability.DELAY,
        Ability.TURN_START,
        Ability.TURN_END,
        Ability.SHOCK,
        Ability.SUPPORT,
        Ability.TURBO,
        Ability.BULLSEYE,
        Ability.PROGRAM,
    }),
    'spell': frozenset({
        Ability.MAGIC,
        Ability.TURBO,
    }),
    'artifact': frozenset({
        Ability.GAME_START,
        Ability.TURN_START,
        Ability.TURN_END,
    }),
    'enchantment': frozenset({
        Ability.TURN_START,
        Ability.TURN_END,
    }),
}

_MISSING = object()
_VARIABLE_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')


@dataclass(frozen=True, slots=True)
class EventSpec:
    result_type: type[ActionResult]
    live_roles: dict[str, tuple[str, ...]]
    snapshot_roles: dict[str, str]
    value_fields: dict[str, type]


_EVENTS = {
    'card_drawn': EventSpec(
        CardDrawnResult,
        live_roles={
            'subject': ('card_id',),
            'card': ('card_id',),
            'player': ('player_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'card': 'card',
        },
        value_fields={},
    ),
    'card_overdrawn': EventSpec(
        CardOverdrawnResult,
        live_roles={
            'subject': ('card_id',),
            'card': ('card_id',),
            'player': ('player_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'card': 'card',
        },
        value_fields={},
    ),
    'card_revealed': EventSpec(
        CardRevealedResult,
        live_roles={
            'subject': ('card_id',),
            'card': ('card_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'card': 'card',
        },
        value_fields={},
    ),
    'entity_damaged': EventSpec(
        EntityDamagedResult,
        live_roles={
            'subject': ('target_id',),
            'target': ('target_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'target': 'target',
        },
        value_fields={
            'amount': int,
            'killed': bool,
            'excess_damage': int,
            'kind': DamageKind,
        },
    ),
    'entity_healed': EventSpec(
        EntityHealedResult,
        live_roles={
            'subject': ('target_id',),
            'target': ('target_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'target': 'target',
        },
        value_fields={
            'amount': int,
        },
    ),
    'dodge_consumed': EventSpec(
        DodgeConsumedResult,
        live_roles={
            'subject': ('monster_id',),
            'monster': ('monster_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'monster': 'monster',
        },
        value_fields={},
    ),
    'attack_declared': EventSpec(
        AttackDeclaredResult,
        live_roles={
            'subject': ('attacker_id',),
            'attacker': ('attacker_id',),
            'defender': ('defender_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'attacker': 'attacker',
            'defender': 'defender',
        },
        value_fields={},
    ),
    'attack_resolved': EventSpec(
        AttackResolvedResult,
        live_roles={
            'subject': ('attacker_id',),
            'attacker': ('attacker_id',),
            'defender': ('defender_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'attacker': 'attacker',
            'defender': 'defender',
        },
        value_fields={
            'damage_to_attacker': int,
            'damage_to_defender': int,
            'attacker_dead': bool,
            'defender_dead': bool,
        },
    ),
    'card_played': EventSpec(
        CardPlayedResult,
        live_roles={
            'subject': ('card_id',),
            'card': ('card_id',),
            'player': ('player_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'card': 'card',
        },
        value_fields={
            'has_need_condition': bool,
            'need_fulfilled': bool,
        },
    ),
    'monster_summoned': EventSpec(
        MonsterSummonedResult,
        live_roles={
            'subject': ('monster_id',),
            'monster': ('monster_id',),
            'player': ('player_id',),
            'target': ('target', 'id'),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'monster': 'monster',
            'target': 'target',
        },
        value_fields={
            'is_played': bool,
        },
    ),
    'spell_cast': EventSpec(
        SpellCastResult,
        live_roles={
            'subject': ('card_id',),
            'card': ('card_id',),
            'player': ('player_id',),
            'target': ('target', 'id'),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'card': 'card',
            'target': 'target',
        },
        value_fields={
            'is_played': bool,
        },
    ),
    'monster_killed': EventSpec(
        MonsterKilledResult,
        live_roles={
            'subject': ('monster_id',),
            'monster': ('monster_id',),
            'killer': ('killer_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'monster': 'monster',
            'killer': 'killer',
        },
        value_fields={
            'cause': KillCause,
        },
    ),
    'gold_spent': EventSpec(
        GoldSpentResult,
        live_roles={
            'player': ('player_id',),
            'card': ('card', 'id'),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'card': 'card',
        },
        value_fields={
            'amount': int,
            'reason': str,
            'is_generated': bool,
        },
    ),
    'ability_triggered': EventSpec(
        AbilityTriggeredResult,
        live_roles={
            'subject': ('entity_id',),
            'entity': ('entity_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'entity': 'entity',
        },
        value_fields={
            'ability': Ability,
        },
    ),
    'board_slot_enchanted': EventSpec(
        BoardSlotEnchantedResult,
        live_roles={
            'player': ('player_id',),
            'slot': ('slot_id',),
            'enchantment': ('enchantment_id',),
            'replaced_enchantment': ('replaced_enchantment', 'id'),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'slot': 'slot',
            'enchantment': 'enchantment',
            'replaced_enchantment': 'replaced_enchantment',
        },
        value_fields={},
    ),
    'enchantment_removed': EventSpec(
        EnchantmentRemovedResult,
        live_roles={
            'player': ('player_id',),
            'slot': ('slot_id',),
            'enchantment': ('enchantment_id',),
        },
        snapshot_roles={
            'subject': 'history_subject',
            'slot': 'slot',
            'enchantment': 'enchantment',
        },
        value_fields={
            'reason': str,
        },
    ),
}

_VALUE_ENUMS = {
    'ability': Ability,
    'artifactRarity': ArtifactRarity,
    'cardKeyword': CardKeyword,
    'cardRarity': CardRarity,
    'cardStatus': CardStatusId,
    'cardZone': CardZone,
    'damageKind': DamageKind,
    'expansion': Expansion,
    'killCause': KillCause,
    'tribe': Tribe,
}

_VALUE_CHOICES = {
    'goldSpendReason': frozenset({
        'play_monster',
        'play_spell',
        'program',
        'effect',
    }),
    'enchantmentRemovalReason': frozenset({
        'expired',
        'removed',
        'replaced',
        'transformed',
    }),
    'soul': frozenset({
        'KINDNESS',
        'DETERMINATION',
        'PATIENCE',
        'BRAVERY',
        'INTEGRITY',
        'PERSEVERANCE',
        'JUSTICE',
    }),
}

_CANDIDATE_VALUES = {
    'id': (ID, int),
    'templateId': (TEMPLATE_ID, int),
    'name': (AttrValue('name'), str),
    'rarity': (RARITY, CardRarity),
    'cost': (COST, int),
    'attack': (ATTACK, int),
    'hp': (HP, int),
    'maxHp': (AttrValue('max_hp'), int),
    'missingHp': (AttrValue('hp_missing'), int),
    'age': (AttrValue('age'), int),
    'position': (AttrValue('pos'), int),
    'controller': (AttrValue('controller_id'), int),
    'creator': (CREATOR_ID, int),
    'gold': (AttrValue('gold'), int),
    'turn': (AttrValue('turn'), int),
    'counter': (AttrValue('counter'), int),
    'questGoal': (AttrValue('quest_goal'), int),
}

_SELECTOR_ATTRIBUTES = {
    'id': ('id', int),
    'templateId': ('template_id', int),
    'name': ('name', str),
    'rarity': ('rarity', CardRarity),
    'cost': ('cost', int),
    'attack': ('attack', int),
    'hp': ('hp', int),
    'maxHp': ('max_hp', int),
    'missingHp': ('hp_missing', int),
    'age': ('age', int),
    'position': ('pos', int),
    'controller': ('controller_id', int),
    'creator': ('creator_id', int),
    'gold': ('gold', int),
    'turn': ('turn', int),
    'counter': ('counter', int),
    'questGoal': ('quest_goal', int),
}

_SIMPLE_SELECTORS = {
    'selector.self': SELF,
    'selector.you': YOU,
    'selector.opponent': OPPONENT,
    'selector.turn_player': TURN_PLAYER,
    'selector.all_players': ALL_PLAYERS,
    'selector.ally_monsters': ALLY_MONSTERS,
    'selector.enemy_monsters': ENEMY_MONSTERS,
    'selector.all_monsters': ALL_MONSTERS,
    'selector.allies': ALLIES,
    'selector.enemies': ENEMIES,
    'selector.hand': HAND,
    'selector.deck': DECK,
    'selector.ally_slots': ALLY_SLOTS,
    'selector.enemy_slots': ENEMY_SLOTS,
    'selector.all_slots': ALL_SLOTS,
    'selector.this_slot_monster': THIS_SLOT_MONSTER,
    'selector.all_enchantments': ALL_ENCHANTMENTS,
    'selector.card_library': CARD_LIBRARY,
    'selector.next_lost_soul': NEXT_LOST_SOUL,
    'selector.choice_selected': CHOICE_SELECTED,
    'selector.choice_not_selected': CHOICE_NOT_SELECTED,
    'selector.killer': KILLER,
    'selector.attacker': ATTACKER,
    'selector.defender': DEFENDER,
    'selector.loop_copy': LOOP_COPY,
    'selector.trigger_card': TRIGGER_CARD,
    'selector.death_slot': DEATH_SLOT,
}

_NAMED_SELECTORS = {
    'selector.card_by_name': ('card', CARD_BY_NAME),
    'selector.artifact_by_name': ('artifact', ARTIFACT_BY_NAME),
    'selector.enchantment_by_name': ('enchantment', ENCHANTMENT_BY_NAME),
}

_BOARD_RELATIONS = {
    'left': LEFT,
    'right': RIGHT,
    'adjacent': ADJACENT,
    'front': FRONT,
    'left_of': LEFT_OF,
    'right_of': RIGHT_OF,
}

_HAND_RELATIONS = {
    'left': LEFT_IN_HAND,
    'right': RIGHT_IN_HAND,
    'adjacent': ADJACENT_IN_HAND,
    'left_of': LEFT_OF_HAND,
    'right_of': RIGHT_OF_HAND,
}

_SIMPLE_PREDICATES = {
    'predicate.is_monster': IS_MONSTER,
    'predicate.is_spell': IS_SPELL,
    'predicate.damaged': DAMAGED,
    'predicate.dead': DEAD,
    'predicate.has_negative_effects': HAS_NEGATIVE_EFFECTS,
    'predicate.has_any_tribe': HAS_ANY_TRIBE,
}


@dataclass(slots=True)
class NodeBudget:
    total: int = 0


@dataclass(frozen=True, slots=True)
class ActionSpec:
    action_type: type[Action]
    selectors: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    enums: tuple[tuple[str, type[Enum]], ...] = ()
    choices: tuple[tuple[str, tuple[Any, ...]], ...] = ()
    fixed: tuple[tuple[str, Any], ...] = ()


_ACTIONS = {
    # Damage and healing
    'action.hit': ActionSpec(
        Hit,
        selectors=('target',),
        values=('damage',),
    ),
    'action.heal': ActionSpec(
        Heal,
        selectors=('target',),
        values=('amount',),
    ),
    'action.kill': ActionSpec(
        Kill,
        selectors=('target',),
    ),
    'action.attack': ActionSpec(
        Attack,
        selectors=('attacker', 'defender'),
    ),
    'action.refresh_attacks': ActionSpec(
        RefreshAttacks,
        selectors=('target',),
    ),

    # Card stats, keywords, and statuses
    'action.buff': ActionSpec(
        Buff,
        selectors=('target',),
        values=('cost', 'attack', 'hp'),
    ),
    'action.set_stats': ActionSpec(
        SetStats,
        selectors=('target',),
        values=('cost', 'attack', 'hp'),
    ),
    'action.set_base_stats': ActionSpec(
        SetBaseStats,
        selectors=('target',),
        values=('cost', 'attack', 'hp'),
    ),
    'action.swap_stats': ActionSpec(
        SwapStats,
        selectors=('target',),
    ),
    'action.halve_stats': ActionSpec(
        HalveStats,
        selectors=('target',),
        values=('round_up', 'halve_cost'),
    ),
    'action.add_keyword': ActionSpec(
        AddKeyword,
        selectors=('target',),
        enums=(('keyword', CardKeyword),),
    ),
    'action.remove_keyword': ActionSpec(
        RemoveKeyword,
        selectors=('target',),
        enums=(('keyword', CardKeyword),),
    ),
    'action.set_status': ActionSpec(
        SetStatus,
        selectors=('target',),
        values=('value',),
        enums=(('status_id', CardStatusId),),
    ),
    'action.remove_status': ActionSpec(
        RemoveStatus,
        selectors=('target',),
        enums=(('status_id', CardStatusId),),
    ),
    'action.silence': ActionSpec(
        Silence,
        selectors=('target',),
    ),
    'action.paralyze': ActionSpec(
        Paralyze,
        selectors=('target',),
    ),
    'action.remove_negative_effects': ActionSpec(
        RemoveNegativeEffects,
        selectors=('target',),
    ),

    # Draw, move, and create cards
    'action.reveal': ActionSpec(
        Reveal,
        selectors=('card',),
    ),
    'action.draw': ActionSpec(
        Draw,
        selectors=('player', 'card'),
    ),
    'action.draw_next': ActionSpec(
        DrawNext,
        selectors=('player',),
        choices=(('from_pos', ('top', 'bottom')),),
    ),
    'action.take_fatigue_damage': ActionSpec(
        TakeFatigueDamage,
        selectors=('player',),
    ),
    'action.move': ActionSpec(
        Move,
        selectors=('target', 'controller'),
        enums=(('zone', CardZone),),
    ),
    'action.swap_cards': ActionSpec(
        SwapCards,
        selectors=('card1', 'card2'),
    ),
    'action.erase': ActionSpec(
        Erase,
        selectors=('target',),
    ),
    'action.summon': ActionSpec(
        Summon,
        selectors=('card', 'controller'),
        values=('pos',),
    ),
    'action.cast': ActionSpec(
        Cast,
        selectors=('card', 'controller', 'effect_target'),
    ),
    'action.transform_card': ActionSpec(
        TransformCard,
        selectors=('target', 'new_card'),
    ),
    'action.catch': ActionSpec(
        Catch,
        selectors=('catcher', 'card_to_catch'),
    ),

    # Choices and players
    'action.choose': ActionSpec(
        Choose,
        selectors=('player', 'options'),
    ),
    'action.set_player_hp': ActionSpec(
        SetPlayerHP,
        selectors=('player',),
        values=('hp',),
    ),
    'action.earn_gold': ActionSpec(
        EarnGold,
        selectors=('player',),
        values=('amount',),
    ),
    'action.spend_gold': ActionSpec(
        SpendGold,
        selectors=('player',),
        values=('amount',),
    ),
    'action.set_gold': ActionSpec(
        SetGold,
        selectors=('player',),
        values=('amount',),
    ),
    'action.skip_next_turn': ActionSpec(
        SkipNextTurn,
        selectors=('player',),
    ),

    # Abilities and Delay
    'action.trigger_ability': ActionSpec(
        TriggerAbility,
        selectors=('target',),
        enums=(('ability', Ability),),
    ),
    'action.toggle_ability': ActionSpec(
        ToggleAbility,
        selectors=('target',),
        values=('enabled',),
        enums=(('ability', CardToggleableAbility),),
    ),
    'action.schedule_delay': ActionSpec(
        ScheduleEffect,
        selectors=('target',),
        fixed=(('name', 'delay'),),
    ),

    # Artifacts
    'action.add_artifact': ActionSpec(
        AddArtifact,
        selectors=('player', 'artifact'),
    ),
    'action.toggle_artifact': ActionSpec(
        ToggleArtifact,
        selectors=('artifact',),
        values=('enabled',),
    ),
    'action.transform_artifact': ActionSpec(
        TransformArtifact,
        selectors=('artifact', 'new_artifact'),
        fixed=(('player', YOU),),
    ),
    'action.update_artifact_counter': ActionSpec(
        UpdateArtifactCounter,
        selectors=('artifact',),
        values=('delta',),
    ),

    # Enchantments
    'action.enchant': ActionSpec(
        Enchant,
        selectors=('slot', 'enchantment'),
    ),
    'action.remove_enchantment': ActionSpec(
        RemoveEnchantment,
        selectors=('target',),
    ),
    'action.transform_enchantment': ActionSpec(
        TransformEnchantment,
        selectors=('target', 'enchantment'),
    ),
    'action.update_enchantment_counter': ActionSpec(
        UpdateEnchantmentCounter,
        selectors=('enchantment',),
        values=('delta',),
    ),
}


class _CompileAbort(Exception):
    pass


def _comparison(left: ValueExpr, operator: str, right: ValueExpr) -> Predicate:
    if operator == 'eq':
        return left == right
    if operator == 'ne':
        return left != right
    if operator == 'lt':
        return left < right
    if operator == 'le':
        return left <= right
    if operator == 'gt':
        return left > right
    if operator == 'ge':
        return left >= right

    raise ValueError(f"Unknown comparison operator {operator!r}")


class IRCompiler:
    def __init__(
        self,
        entity: ParsedEntity,
        *,
        base: ContentCatalog,
        entities: list[ParsedEntity],
        validation: ValidationContext,
        budget: NodeBudget,
    ):
        self.entity = entity
        self.validation = validation
        self.budget = budget

        self.entity_node_count = 0
        self.scoped_variable_count = 0
        self.variables: dict[str, Var] = {}
        self.event_name: str | None = None

        self.available_names = {
            'card': {
                normalize_content_name(template.name)
                for template in base.cards.templates
            },
            'artifact': {
                normalize_content_name(artifact.name)
                for artifact in base.artifacts.values()
            },
            'enchantment': {
                normalize_content_name(enchantment.name)
                for enchantment in base.enchantments.values()
            },
        }

        for parsed in entities:
            kind = 'card' if parsed.kind in ('monster', 'spell') else parsed.kind
            self.available_names[kind].add(
                normalize_content_name(parsed.definition['name'])
            )

    def _fail(
        self,
        code: str,
        message: str,
        *,
        path: str,
        node_id: str | None = None,
    ) -> None:
        self.validation.error(
            code,
            message,
            path=path,
            entity_id=self.entity.content_id,
            node_id=node_id,
        )
        raise _CompileAbort

    def _node_id(
        self,
        raw: dict[str, Any],
        *,
        path: str,
    ) -> str | None:
        node_id = raw.get('nodeId')
        if node_id is None:
            return None

        if type(node_id) is not str:
            self._fail(
                'INVALID_NODE_ID',
                "A semantic node ID must be a string.",
                path=f"{path}.nodeId",
            )

        if len(node_id) > 128:
            self._fail(
                'INVALID_NODE_ID',
                "A semantic node ID cannot exceed 128 characters.",
                path=f"{path}.nodeId",
                node_id=node_id,
            )

        return node_id

    def _node(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
    ) -> tuple[str, str | None]:
        if type(raw) is not dict:
            self._fail(
                'EXPECTED_NODE',
                "Expected a semantic IR node object.",
                path=path,
            )

        node_id = self._node_id(raw, path=path)

        if depth > self.validation.limits.max_ir_depth:
            self._fail(
                'IR_DEPTH_EXCEEDED',
                "Semantic IR nesting is too deep.",
                path=path,
                node_id=node_id,
            )

        self.entity_node_count += 1
        self.budget.total += 1

        if self.entity_node_count > self.validation.limits.max_ir_nodes_per_entity:
            self._fail(
                'ENTITY_NODE_LIMIT_EXCEEDED',
                "This entity contains too many semantic IR nodes.",
                path=path,
                node_id=node_id,
            )

        if self.budget.total > self.validation.limits.max_ir_nodes_per_pack:
            self._fail(
                'PACK_NODE_LIMIT_EXCEEDED',
                "The content pack contains too many semantic IR nodes.",
                path=path,
                node_id=node_id,
            )

        node = raw.get('node')
        if type(node) is not str:
            self._fail(
                'INVALID_NODE_NAME',
                "A semantic IR node requires a string node field.",
                path=f"{path}.node",
                node_id=node_id,
            )

        return node, node_id

    def _enum(
        self,
        raw: Any,
        enum_type: type[Enum],
        *,
        path: str,
        node_id: str | None,
    ) -> Enum:
        if type(raw) is not str or raw not in enum_type.__members__:
            self._fail(
                'UNKNOWN_ENUM_VALUE',
                f"Unknown {enum_type.__name__} value {raw!r}.",
                path=path,
                node_id=node_id,
            )

        return enum_type[raw]

    def _variable(
        self,
        raw: Any,
        *,
        path: str,
        node_id: str | None,
        expected_type: type[Var] | None = None,
    ) -> Var:
        if type(raw) is not str:
            self._fail(
                'INVALID_VARIABLE_REFERENCE',
                "A variable reference must be a string.",
                path=path,
                node_id=node_id,
            )

        variable = self.variables.get(raw)
        if variable is None:
            self._fail(
                'UNKNOWN_VARIABLE',
                f"Variable {raw!r} is not declared.",
                path=path,
                node_id=node_id,
            )

        if expected_type is not None and not isinstance(variable, expected_type):
            expected_name = 'selector' if expected_type is SelectorVar else 'value'
            self._fail(
                'INVALID_VARIABLE_TYPE',
                f"Variable {raw!r} is not a {expected_name} variable.",
                path=path,
                node_id=node_id,
            )

        return variable

    def _event_spec(
        self,
        *,
        path: str,
        node_id: str | None,
    ) -> EventSpec:
        if self.event_name is None:
            self._fail(
                'EVENT_NOT_AVAILABLE',
                "Event context is only available inside an event reaction.",
                path=path,
                node_id=node_id,
            )

        return _EVENTS[self.event_name]

    @staticmethod
    def _event_value(path: tuple[str, ...]) -> ValueExpr:
        value = EVENT
        for name in path:
            value = getattr(value, name)

        return value

    def _selector_input(
        self,
        raw: dict[str, Any],
        name: str,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> TargetSelector:
        return self._selector(
            raw[name],
            path=f"{path}.{name}",
            depth=depth + 1,
            allow_target=allow_target,
        )

    def _predicate_input(
        self,
        raw: dict[str, Any],
        name: str,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> Predicate:
        return self._predicate(
            raw[name],
            path=f"{path}.{name}",
            depth=depth + 1,
            allow_target=allow_target,
        )

    def _value_input(
        self,
        raw: dict[str, Any],
        name: str,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> ValueExpr:
        return self._value(
            raw[name],
            path=f"{path}.{name}",
            depth=depth + 1,
            allow_target=allow_target,
        )

    def _effect_input(
        self,
        raw: dict[str, Any],
        name: str,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> Any:
        return self._effect(
            raw[name],
            path=f"{path}.{name}",
            depth=depth + 1,
            allow_target=allow_target,
        )

    def _optional_effect(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> Any | None:
        if raw is None:
            return None

        return self._effect(
            raw,
            path=path,
            depth=depth,
            allow_target=allow_target,
        )

    def _literal_count(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
    ) -> int:
        node, node_id = self._node(raw, path=path, depth=depth)
        value = raw.get('value')
        if (
            node != 'value.literal'
            or type(value) is not int
            or not 0 <= value <= self.validation.limits.max_iteration_count
        ):
            self._fail(
                'UNBOUNDED_ITERATION',
                (
                    "A bounded count must be an integer literal between 0 and "
                    f"{self.validation.limits.max_iteration_count}."
                ),
                path=path,
                node_id=node_id,
            )

        return value

    def _content_name(
        self,
        raw: Any,
        kind: str,
        *,
        path: str,
        node_id: str | None,
    ) -> str:
        if type(raw) is not str:
            self._fail(
                'INVALID_CONTENT_NAME',
                "A content display name must be a string.",
                path=path,
                node_id=node_id,
            )

        name = raw.strip()
        if not name or len(name) > self.validation.limits.max_name_length:
            self._fail(
                'INVALID_CONTENT_NAME',
                "A content display name is empty or too long.",
                path=path,
                node_id=node_id,
            )

        if normalize_content_name(name) not in self.available_names[kind]:
            self._fail(
                'UNKNOWN_CONTENT_NAME',
                f"No {kind} named {name!r} exists in this catalog.",
                path=path,
                node_id=node_id,
            )

        return name

    def _compare(
        self,
        left: ValueExpr,
        operator: str,
        right: ValueExpr,
        *,
        path: str,
        node_id: str | None,
    ) -> Predicate:
        try:
            return _comparison(left, operator, right)
        except ValueError as exc:
            self._fail(
                'INVALID_COMPARISON_OPERATOR',
                str(exc),
                path=path,
                node_id=node_id,
            )

    @contextmanager
    def _scoped_variable(
        self,
        name: Any,
        type_: type,
        *,
        path: str,
        node_id: str | None,
    ):
        if type(name) is not str or _VARIABLE_NAME.fullmatch(name) is None:
            self._fail(
                'INVALID_VARIABLE_NAME',
                (
                    "Variable names must contain at most 64 letters, "
                    "numbers, or underscores and cannot begin with a number."
                ),
                path=path,
                node_id=node_id,
            )

        variable = Var(type_)
        variable.name = f'_scripted_scoped_variable_{self.scoped_variable_count}'
        self.scoped_variable_count += 1

        old = self.variables.get(name, _MISSING)
        self.variables[name] = variable

        try:
            yield variable
        finally:
            if old is _MISSING:
                self.variables.pop(name, None)
            else:
                self.variables[name] = old

    def _inferred_value_type(self, raw: Any) -> type:
        if type(raw) is not dict:
            return object

        node = raw.get('node')
        if node == 'value.literal':
            value = raw.get('value')
            return bool if type(value) is bool else int

        if node == 'variable.reference':
            variable = self.variables.get(raw.get('variable'))
            return object if variable is None else variable.type

        if node == 'value.enum':
            return _VALUE_ENUMS.get(raw.get('enum'), str)

        if node == 'value.event' and self.event_name is not None:
            return _EVENTS[self.event_name].value_fields.get(raw.get('field'), object)

        if node == 'value.candidate_attribute':
            return _CANDIDATE_VALUES.get(raw.get('attribute'), (None, object))[1]

        if node == 'value.attribute':
            return _SELECTOR_ATTRIBUTES.get(raw.get('attribute'), (None, object))[1]

        if node == 'value.unique_values':
            return self._inferred_value_type(raw.get('value'))

        if node == 'value.unique_tribes':
            return Tribe

        if node in ('value.min', 'value.max'):
            return self._inferred_value_type(raw.get('value'))

        if node in (
            'value.count',
            'value.status',
            'value.base_stat',
            'value.buff',
            'value.empty_slots',
            'value.sum',
            'value.count_distinct',
            'value.count_unique_tribes',
            'value.math',
            'value.negate',
            'value.clamp',
            'value.least',
            'value.greatest',
        ):
            return int

        if node in ('value.exists', 'value.synergy_triggered'):
            return bool

        if node == 'value.player_soul':
            return str

        return object

    @staticmethod
    def _boolean_condition(
        condition: Predicate | TargetSelector | ValueExpr,
    ) -> ValueExpr:
        if isinstance(condition, Predicate):
            return PredicateAsValueExpr(condition)

        if isinstance(condition, (TargetSelector, ValueExpr)):
            return BooleanValue(condition)

        raise TypeError(
            f"Expected a Predicate, TargetSelector, or ValueExpr, got {type(condition).__name__}"
        )

    def _iterable(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> tuple[Any, type]:
        node = raw.get('node') if type(raw) is dict else None

        if node == 'variable.reference':
            variable = self.variables.get(raw.get('variable'))
            if isinstance(variable, SelectorVar):
                return (
                    self._selector(
                        raw,
                        path=path,
                        depth=depth,
                        allow_target=allow_target,
                    ),
                    TargetSelector,
                )

        if type(node) is str and node.startswith('selector.'):
            return (
                self._selector(
                    raw,
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                TargetSelector,
            )

        if node in ('value.unique_values', 'value.unique_tribes'):
            return (
                self._value(
                    raw,
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                self._inferred_value_type(raw),
            )

        self._fail(
            'INVALID_ITERABLE',
            "ForEach requires a Selector or a typed unique-value list.",
            path=path,
            node_id=raw.get('nodeId') if type(raw) is dict else None,
        )

    def _selector(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> TargetSelector:
        node, node_id = self._node(raw, path=path, depth=depth)

        selector = _SIMPLE_SELECTORS.get(node)
        if selector is not None:
            return selector

        named_selector = _NAMED_SELECTORS.get(node)
        if named_selector is not None:
            kind, factory = named_selector
            name = self._content_name(
                raw.get('name'),
                kind,
                path=f"{path}.name",
                node_id=node_id,
            )
            return factory(name)

        if node == 'selector.target':
            if not allow_target:
                self._fail(
                    'TARGET_NOT_AVAILABLE',
                    "TARGET is not available here.",
                    path=path,
                    node_id=node_id,
                )

            return TARGET

        if node == 'variable.reference':
            return self._variable(
                raw.get('variable'),
                path=f"{path}.variable",
                node_id=node_id,
                expected_type=SelectorVar,
            )

        if node == 'selector.zone':
            player = self._selector_input(
                raw,
                'player',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            zone = self._enum(
                raw.get('zone'),
                CardZone,
                path=f"{path}.zone",
                node_id=node_id,
            )
            factory = {
                CardZone.BOARD: BOARD_OF,
                CardZone.HAND: HAND_OF,
                CardZone.DECK: DECK_OF,
                CardZone.DUSTPILE: DUSTPILE_OF,
                CardZone.ERASED: ERASED_OF,
            }.get(zone)

            if factory is None:
                self._fail(
                    'UNSUPPORTED_ZONE',
                    f"Scripted zone selection does not support {zone.name}.",
                    path=f"{path}.zone",
                    node_id=node_id,
                )

            return factory(player)

        if node in ('selector.controller_of', 'selector.opponent_of'):
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            if node == 'selector.controller_of':
                return CONTROLLER_OF(selector)

            return OPPONENT_OF(selector)

        if node == 'selector.artifact_of_player':
            player = self._selector_input(
                raw,
                'player',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            name = self._content_name(
                raw.get('name'),
                'artifact',
                path=f"{path}.name",
                node_id=node_id,
            )
            return ARTIFACT_OF_PLAYER(player, name)

        if node in ('selector.board_slots_of', 'selector.enchantments_of'):
            player = self._selector_input(
                raw,
                'player',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            if node == 'selector.board_slots_of':
                return BOARD_SLOTS_OF(player)

            return ENCHANTMENTS_OF(player)

        if node == 'selector.relative_board':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            operation = _BOARD_RELATIONS.get(raw.get('relation'))
            if operation is None:
                self._fail(
                    'UNKNOWN_RELATION',
                    f"Unknown board relation {raw.get('relation')!r}.",
                    path=f"{path}.relation",
                    node_id=node_id,
                )

            return operation(selector)

        if node == 'selector.relative_hand':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            operation = _HAND_RELATIONS.get(raw.get('relation'))
            if operation is None:
                self._fail(
                    'UNKNOWN_RELATION',
                    f"Unknown hand relation {raw.get('relation')!r}.",
                    path=f"{path}.relation",
                    node_id=node_id,
                )

            return operation(selector)

        if node == 'selector.slot_of':
            return SLOT_OF(self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            ))

        if node in ('selector.monster_in_slot', 'selector.enchantment_in_slot'):
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            if node == 'selector.monster_in_slot':
                return MONSTER_IN_SLOT(selector)

            return ENCHANTMENT_IN_SLOT(selector)

        if node == 'selector.event_entity':
            spec = self._event_spec(path=path, node_id=node_id)
            role = raw.get('role')
            event_path = spec.live_roles.get(role)
            if event_path is None:
                self._fail(
                    'UNKNOWN_EVENT_ROLE',
                    f"Event {self.event_name!r} does not expose live role {role!r}.",
                    path=f"{path}.role",
                    node_id=node_id,
                )

            return RESOLVE_ENTITY(self._event_value(event_path))

        if node == 'selector.event_snapshot':
            spec = self._event_spec(path=path, node_id=node_id)
            role = raw.get('role')
            field = spec.snapshot_roles.get(role)
            if field is None:
                self._fail(
                    'UNKNOWN_EVENT_ROLE',
                    f"Event {self.event_name!r} does not expose snapshot role {role!r}.",
                    path=f"{path}.role",
                    node_id=node_id,
                )

            if field == 'history_subject':
                return EVENT.subject

            return EVENT.select(field)

        if node == 'selector.filter':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            predicate = self._predicate_input(
                raw,
                'predicate',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            return selector & predicate

        if node in (
            'selector.union',
            'selector.intersection',
            'selector.difference',
        ):
            left = self._selector_input(
                raw,
                'left',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            right = self._selector_input(
                raw,
                'right',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

            if node == 'selector.union':
                return left | right
            if node == 'selector.intersection':
                return left & right

            return left & ~right

        if node == 'selector.index':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            index = self._value_input(
                raw,
                'index',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            return selector[index - 1]

        if node == 'selector.take':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            count = self._literal_count(
                raw['count'],
                path=f"{path}.count",
                depth=depth + 1,
            )

            if raw.get('side') == 'first':
                return selector.top(count)
            if raw.get('side') == 'last':
                return selector.bottom(count)

            self._fail(
                'UNKNOWN_SELECTION_SIDE',
                "selector.take side must be first or last.",
                path=f"{path}.side",
                node_id=node_id,
            )

        if node in ('selector.leftmost', 'selector.rightmost'):
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            return selector >> (
                LEFTMOST
                if node == 'selector.leftmost'
                else RIGHTMOST
            )

        if node in (
            'selector.random',
            'selector.min',
            'selector.max',
            'selector.sort_by',
            'selector.distinct',
        ):
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

            if node == 'selector.random':
                count = self._value_input(
                    raw,
                    'count',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                )
                return selector >> RANDOM(count)

            key = self._value_input(
                raw,
                'key',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

            if node == 'selector.min':
                count = self._value_input(
                    raw,
                    'count',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                )
                return selector >> MIN(key, n=count)

            if node == 'selector.max':
                count = self._value_input(
                    raw,
                    'count',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                )
                return selector >> MAX(key, n=count)

            if node == 'selector.sort_by':
                reverse = raw.get('reverse', False)
                if type(reverse) is not bool:
                    self._fail(
                        'INVALID_SORT_DIRECTION',
                        "selector.sort_by reverse must be a boolean.",
                        path=f"{path}.reverse",
                        node_id=node_id,
                    )

                return selector >> SORT_BY(
                    key,
                    reverse=reverse,
                )

            return selector >> DISTINCT(key)

        if node == 'selector.limit_per':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            key = self._value_input(
                raw,
                'key',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            count = self._value_input(
                raw,
                'count',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            return selector >> LIMIT_PER(key, count)

        if node == 'selector.generate':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            controller = self._selector_input(
                raw,
                'controller',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            count = self._literal_count(
                raw['count'],
                path=f"{path}.count",
                depth=depth + 1,
            )
            return GENERATE_CARD(
                selector,
                controller=controller,
                count=count,
            )

        if node == 'selector.discover':
            controller = self._selector_input(
                raw,
                'controller',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            count = self._literal_count(
                raw['count'],
                path=f"{path}.count",
                depth=depth + 1,
            )

            constraints = ()
            if raw.get('predicate') is not None:
                constraints = (
                    self._predicate(
                        raw['predicate'],
                        path=f"{path}.predicate",
                        depth=depth + 1,
                        allow_target=allow_target,
                    ),
                )

            return DISCOVER(
                *constraints,
                n=count,
                controller=controller,
            )

        if node in ('selector.copy', 'selector.exact_copy'):
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            transform = COPY() if node == 'selector.copy' else EXACT_COPY()
            return selector >> transform

        self._fail(
            'UNKNOWN_SELECTOR_NODE',
            f"Unsupported selector node {node!r}.",
            path=path,
            node_id=node_id,
        )

    def _predicate(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> Predicate:
        node, node_id = self._node(raw, path=path, depth=depth)

        predicate = _SIMPLE_PREDICATES.get(node)
        if predicate is not None:
            return predicate

        if node == 'predicate.has_keyword':
            return HAS_KEYWORD(self._enum(
                raw.get('keyword'),
                CardKeyword,
                path=f"{path}.keyword",
                node_id=node_id,
            ))

        if node == 'predicate.has_status':
            return HAS_STATUS(self._enum(
                raw.get('status'),
                CardStatusId,
                path=f"{path}.status",
                node_id=node_id,
            ))

        if node == 'predicate.has_tribe':
            return HAS_TRIBE(self._enum(
                raw.get('tribe'),
                Tribe,
                path=f"{path}.tribe",
                node_id=node_id,
            ))

        if node == 'predicate.has_ability':
            return HAS_ABILITY(self._enum(
                raw.get('ability'),
                Ability,
                path=f"{path}.ability",
                node_id=node_id,
            ))

        if node == 'predicate.expansion':
            return EXPANSION(self._enum(
                raw.get('expansion'),
                Expansion,
                path=f"{path}.expansion",
                node_id=node_id,
            ))

        if node == 'predicate.rarity':
            rarity = self._enum(
                raw.get('rarity'),
                CardRarity,
                path=f"{path}.rarity",
                node_id=node_id,
            )
            return self._compare(
                RARITY,
                raw.get('operator'),
                to_value(rarity),
                path=f"{path}.operator",
                node_id=node_id,
            )

        if node == 'predicate.generated':
            generated = raw.get('generated')
            if type(generated) is not bool:
                self._fail(
                    'INVALID_GENERATED_FLAG',
                    "predicate.generated requires a boolean generated field.",
                    path=f"{path}.generated",
                    node_id=node_id,
                )

            return GENERATED if generated else NON_GENERATED

        if node == 'predicate.generated_by':
            creator = self._selector_input(
                raw,
                'creator',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            return GENERATED_BY(creator)

        if node == 'predicate.slot_state':
            predicate = {
                'empty': EMPTY_SLOT,
                'occupied': OCCUPIED_SLOT,
                'enchanted': ENCHANTED_SLOT,
                'unenchanted': UNENCHANTED_SLOT,
            }.get(raw.get('state'))

            if predicate is None:
                self._fail(
                    'UNKNOWN_SLOT_STATE',
                    f"Unknown Board Slot state {raw.get('state')!r}.",
                    path=f"{path}.state",
                    node_id=node_id,
                )

            return predicate

        if node == 'predicate.slot_has_enchantment':
            name = self._content_name(
                raw.get('name'),
                'enchantment',
                path=f"{path}.name",
                node_id=node_id,
            )
            return SLOT_HAS_ENCHANTMENT(name)

        if node == 'predicate.has_artifact':
            name = self._content_name(
                raw.get('name'),
                'artifact',
                path=f"{path}.name",
                node_id=node_id,
            )
            return self._compare(
                HAS_ARTIFACT(name),
                'eq',
                to_value(True),
                path=path,
                node_id=node_id,
            )

        if node == 'predicate.attribute_compare':
            value = _CANDIDATE_VALUES.get(raw.get('attribute'))
            if value is None:
                self._fail(
                    'UNKNOWN_ATTRIBUTE',
                    f"Unsupported candidate attribute {raw.get('attribute')!r}.",
                    path=f"{path}.attribute",
                    node_id=node_id,
                )

            return self._compare(
                value[0],
                raw.get('operator'),
                self._value_input(
                    raw,
                    'value',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                path=f"{path}.operator",
                node_id=node_id,
            )

        if node == 'predicate.compare':
            return self._compare(
                self._value_input(
                    raw,
                    'left',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                raw.get('operator'),
                self._value_input(
                    raw,
                    'right',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                path=f"{path}.operator",
                node_id=node_id,
            )

        if node in ('predicate.and', 'predicate.or'):
            values = raw.get('predicates')
            if (
                type(values) is not list
                or not 2 <= len(values) <= self.validation.limits.max_sequence_length
            ):
                self._fail(
                    'INVALID_PREDICATE_LIST',
                    "Boolean predicate nodes require a bounded list of at least two predicates.",
                    path=f"{path}.predicates",
                    node_id=node_id,
                )

            predicates = [
                self._predicate(
                    value,
                    path=f"{path}.predicates[{index}]",
                    depth=depth + 1,
                    allow_target=allow_target,
                )
                for index, value in enumerate(values)
            ]

            result = predicates[0]
            for predicate in predicates[1:]:
                if node == 'predicate.and':
                    result = result & predicate
                else:
                    result = result | predicate

            return result

        if node == 'predicate.not':
            return ~self._predicate_input(
                raw,
                'predicate',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

        self._fail(
            'UNKNOWN_PREDICATE_NODE',
            f"Unsupported predicate node {node!r}.",
            path=path,
            node_id=node_id,
        )

    def _value(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> ValueExpr:
        node, node_id = self._node(raw, path=path, depth=depth)

        if node == 'value.literal':
            value = raw.get('value')
            if type(value) is bool:
                return to_value(value)

            if type(value) is int:
                if abs(value) > self.validation.limits.max_integer_magnitude:
                    self._fail(
                        'INTEGER_OUT_OF_RANGE',
                        "Integer literal exceeds the configured magnitude limit.",
                        path=f"{path}.value",
                        node_id=node_id,
                    )

                return to_value(value)

            self._fail(
                'INVALID_LITERAL',
                "A value.literal must contain an integer or boolean.",
                path=f"{path}.value",
                node_id=node_id,
            )

        if node == 'value.enum':
            enum_name = raw.get('enum')
            member = raw.get('member')
            enum_type = _VALUE_ENUMS.get(enum_name)

            if enum_type is not None:
                return to_value(self._enum(
                    member,
                    enum_type,
                    path=f"{path}.member",
                    node_id=node_id,
                ))

            choices = _VALUE_CHOICES.get(enum_name)
            if choices is None or member not in choices:
                self._fail(
                    'UNKNOWN_ENUM_VALUE',
                    f"Unknown {enum_name!r} value {member!r}.",
                    path=f"{path}.member",
                    node_id=node_id,
                )

            return to_value(member)

        if node == 'variable.reference':
            return self._variable(
                raw.get('variable'),
                path=f"{path}.variable",
                node_id=node_id,
                expected_type=ValueVar,
            )

        if node == 'value.event':
            spec = self._event_spec(path=path, node_id=node_id)
            field = raw.get('field')
            if field not in spec.value_fields:
                self._fail(
                    'UNKNOWN_EVENT_VALUE',
                    f"Event {self.event_name!r} does not expose value {field!r}.",
                    path=f"{path}.field",
                    node_id=node_id,
                )

            return getattr(EVENT, field)

        if node in ('value.count', 'value.exists'):
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            if node == 'value.count':
                return COUNT(selector)

            return EXISTS(selector)

        if node == 'value.candidate_attribute':
            value = _CANDIDATE_VALUES.get(raw.get('attribute'))
            if value is None:
                self._fail(
                    'UNKNOWN_ATTRIBUTE',
                    f"Unsupported candidate attribute {raw.get('attribute')!r}.",
                    path=f"{path}.attribute",
                    node_id=node_id,
                )

            return value[0]

        if node == 'value.attribute':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            value = _SELECTOR_ATTRIBUTES.get(raw.get('attribute'))
            if value is None:
                self._fail(
                    'UNKNOWN_ATTRIBUTE',
                    f"Unsupported selector attribute {raw.get('attribute')!r}.",
                    path=f"{path}.attribute",
                    node_id=node_id,
                )

            return SelectorAttrValue(selector, value[0])

        if node == 'value.base_stat':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            attribute = {
                'cost': 'cost',
                'attack': 'attack',
                'hp': 'hp',
            }.get(raw.get('attribute'))

            if attribute is None:
                self._fail(
                    'UNKNOWN_ATTRIBUTE',
                    f"Unsupported base-stat attribute {raw.get('attribute')!r}.",
                    path=f"{path}.attribute",
                    node_id=node_id,
                )

            return getattr(selector.base, attribute)

        if node == 'value.buff':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            attribute = {
                'cost': 'cost',
                'attack': 'attack',
                'maxHp': 'max_hp',
            }.get(raw.get('attribute'))

            if attribute is None:
                self._fail(
                    'UNKNOWN_ATTRIBUTE',
                    f"Unsupported buff attribute {raw.get('attribute')!r}.",
                    path=f"{path}.attribute",
                    node_id=node_id,
                )

            return getattr(selector.buffs, attribute)

        if node == 'value.status':
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            status = self._enum(
                raw.get('status'),
                CardStatusId,
                path=f"{path}.status",
                node_id=node_id,
            )
            return selector.status(status)

        if node == 'value.empty_slots':
            return EMPTY_SLOTS(self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            ))

        if node == 'value.synergy_triggered':
            return SYNERGY_TRIGGERED

        if node == 'value.player_soul':
            return PLAYER_SOUL(self._selector_input(
                raw,
                'player',
                path=path,
                depth=depth,
                allow_target=allow_target,
            ))

        if node == 'value.math':
            left = self._value_input(
                raw,
                'left',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            right = self._value_input(
                raw,
                'right',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            operator = raw.get('operator')

            if operator == 'add':
                return left + right
            if operator == 'subtract':
                return left - right
            if operator == 'multiply':
                return left * right
            if operator == 'divide':
                return left / right
            if operator == 'floor_divide':
                return left // right
            if operator == 'modulo':
                return left % right

            self._fail(
                'UNKNOWN_MATH_OPERATOR',
                f"Unknown math operator {operator!r}.",
                path=f"{path}.operator",
                node_id=node_id,
            )

        if node == 'value.negate':
            return -self._value_input(
                raw,
                'value',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

        if node == 'value.clamp':
            return CLAMP(
                self._value_input(
                    raw,
                    'value',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                self._value_input(
                    raw,
                    'lower',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                self._value_input(
                    raw,
                    'upper',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
            )

        if node in ('value.least', 'value.greatest'):
            left = self._value_input(
                raw,
                'left',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            right = self._value_input(
                raw,
                'right',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            if node == 'value.least':
                return LEAST(left, right)

            return GREATEST(left, right)

        if node in ('value.sum', 'value.min', 'value.max', 'value.count_distinct'):
            selector = self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            value = self._value_input(
                raw,
                'value',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

            if node == 'value.sum':
                return SUM(selector, value)
            if node == 'value.min':
                return MINVAL(selector, value)
            if node == 'value.max':
                return MAXVAL(selector, value)

            return COUNT_DISTINCT(selector, value)

        if node == 'value.unique_values':
            return UNIQUE_VALUES(
                self._selector_input(
                    raw,
                    'selector',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                self._value_input(
                    raw,
                    'value',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
            )

        if node == 'value.unique_tribes':
            return UNIQUE_TRIBES(self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            ))

        if node == 'value.count_unique_tribes':
            return COUNT_UNIQUE_TRIBES(self._selector_input(
                raw,
                'selector',
                path=path,
                depth=depth,
                allow_target=allow_target,
            ))

        self._fail(
            'UNKNOWN_VALUE_NODE',
            f"Unsupported value node {node!r}.",
            path=path,
            node_id=node_id,
        )

    def _condition(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> Predicate | ValueExpr | TargetSelector:
        if type(raw) is not dict or type(raw.get('node')) is not str:
            self._fail(
                'EXPECTED_CONDITION',
                "Expected a Predicate, boolean Value, or Selector node.",
                path=path,
            )

        node = raw['node']

        if node in ('predicate.and', 'predicate.or'):
            _, node_id = self._node(raw, path=path, depth=depth)
            values = raw.get('predicates')
            if (
                type(values) is not list
                or not 2 <= len(values) <= self.validation.limits.max_sequence_length
            ):
                self._fail(
                    'INVALID_PREDICATE_LIST',
                    "Boolean condition nodes require a bounded list of at least two conditions.",
                    path=f"{path}.predicates",
                    node_id=node_id,
                )

            conditions = [
                self._condition(
                    value,
                    path=f"{path}.predicates[{index}]",
                    depth=depth + 1,
                    allow_target=allow_target,
                )
                for index, value in enumerate(values)
            ]

            result = self._boolean_condition(conditions[0])
            for condition in conditions[1:]:
                value = self._boolean_condition(condition)
                if node == 'predicate.and':
                    result = result & value
                else:
                    result = result | value

            return result

        if node == 'predicate.not':
            self._node(raw, path=path, depth=depth)
            condition = self._condition(
                raw['predicate'],
                path=f"{path}.predicate",
                depth=depth + 1,
                allow_target=allow_target,
            )
            return ~self._boolean_condition(condition)

        if node == 'variable.reference':
            _, node_id = self._node(raw, path=path, depth=depth)
            return self._variable(
                raw.get('variable'),
                path=f"{path}.variable",
                node_id=node_id,
            )

        if node.startswith('predicate.'):
            return self._predicate(
                raw,
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

        if node.startswith('value.'):
            return self._value(
                raw,
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

        if node.startswith('selector.'):
            return self._selector(
                raw,
                path=path,
                depth=depth,
                allow_target=allow_target,
            )

        _, node_id = self._node(raw, path=path, depth=depth)
        self._fail(
            'EXPECTED_CONDITION',
            "Expected a Predicate, boolean Value, or Selector node.",
            path=path,
            node_id=node_id,
        )

    def _action(
        self,
        node: str,
        raw: dict[str, Any],
        *,
        path: str,
        depth: int,
        node_id: str | None,
        allow_target: bool,
    ) -> Action:
        spec = _ACTIONS[node]
        kwargs = dict(spec.fixed)

        for name in spec.selectors:
            if name not in raw:
                continue

            value = raw[name]
            if node == 'action.cast' and name == 'effect_target' and value == 'random':
                kwargs[name] = value
            else:
                kwargs[name] = self._selector(
                    value,
                    path=f"{path}.{name}",
                    depth=depth + 1,
                    allow_target=allow_target,
                )

        for name in spec.values:
            if name in raw:
                kwargs[name] = self._value(
                    raw[name],
                    path=f"{path}.{name}",
                    depth=depth + 1,
                    allow_target=allow_target,
                )

        for name, enum_type in spec.enums:
            if name in raw:
                kwargs[name] = self._enum(
                    raw[name],
                    enum_type,
                    path=f"{path}.{name}",
                    node_id=node_id,
                )

        for name, choices in spec.choices:
            if name not in raw:
                continue

            value = raw[name]
            if value not in choices:
                self._fail(
                    'INVALID_ACTION_ARGUMENT',
                    f"Action argument {name!r} has unsupported value {value!r}.",
                    path=f"{path}.{name}",
                    node_id=node_id,
                )

            kwargs[name] = value

        try:
            return spec.action_type(**kwargs)
        except TypeError as exc:
            self._fail(
                'INVALID_ACTION',
                str(exc),
                path=path,
                node_id=node_id,
            )

    def _effect(
        self,
        raw: Any,
        *,
        path: str,
        depth: int,
        allow_target: bool,
    ) -> Any:
        node, node_id = self._node(raw, path=path, depth=depth)

        if node == 'effect.noop':
            return NoEffect()

        if node == 'effect.program':
            amount = self._value_input(
                raw,
                'amount',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            effect = self._effect_input(
                raw,
                'effect',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            return Program(amount).to(effect)

        if node == 'effect.switch':
            return Switch(
                self._effect_input(
                    raw,
                    'left',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
                self._effect_input(
                    raw,
                    'right',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                ),
            )

        if node == 'action.draw_up_to':
            return DrawUpTo(self._literal_count(
                raw['count'],
                path=f"{path}.count",
                depth=depth + 1,
            ))

        if node in ('action.fill_board', 'action.fill_hand'):
            player = self._selector_input(
                raw,
                'player',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            card = self._selector_input(
                raw,
                'card',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            if node == 'action.fill_board':
                return FillBoard(player, card)

            return FillHand(player, card)

        if node == 'action.release_caught_card':
            catcher = self._selector_input(
                raw,
                'catcher',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            variable = self._variable(
                raw.get('var'),
                path=f"{path}.var",
                node_id=node_id,
                expected_type=SelectorVar,
            )
            return ReleaseCaughtCard(
                catcher=catcher,
                var=variable,
            )

        if node == 'action.set_variable':
            variable = self._variable(
                raw.get('variable'),
                path=f"{path}.variable",
                node_id=node_id,
            )

            if isinstance(variable, SelectorVar):
                value = self._selector_input(
                    raw,
                    'value',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                )
            elif variable.type is bool:
                value = self._condition(
                    raw['value'],
                    path=f"{path}.value",
                    depth=depth + 1,
                    allow_target=allow_target,
                )
                if isinstance(value, TargetSelector):
                    value = EXISTS(value)
                elif isinstance(value, ValueExpr):
                    value = BooleanValue(value)
            else:
                value = self._value_input(
                    raw,
                    'value',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                )

            return SetVar(var=variable, value=value)

        if node == 'effect.store_result':
            variable = self._variable(
                raw.get('variable'),
                path=f"{path}.variable",
                node_id=node_id,
                expected_type=ValueVar,
            )
            if variable.type is not StepResult:
                self._fail(
                    'INVALID_VARIABLE_TYPE',
                    "Stored action results require an action-result variable.",
                    path=f"{path}.variable",
                    node_id=node_id,
                )

            action = self._effect_input(
                raw,
                'action',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            if not isinstance(action, Action):
                self._fail(
                    'EXPECTED_ACTION',
                    "effect.store_result requires one Action node.",
                    path=f"{path}.action",
                    node_id=node_id,
                )

            return action.store_result(variable)

        if node == 'effect.sequence':
            values = raw.get('effects')
            if (
                type(values) is not list
                or not 1 <= len(values) <= self.validation.limits.max_sequence_length
            ):
                self._fail(
                    'INVALID_EFFECT_LIST',
                    "effect.sequence requires a bounded non-empty effect list.",
                    path=f"{path}.effects",
                    node_id=node_id,
                )

            effects = [
                self._effect(
                    value,
                    path=f"{path}.effects[{index}]",
                    depth=depth + 1,
                    allow_target=allow_target,
                )
                for index, value in enumerate(values)
            ]

            result = effects[0]
            for effect in effects[1:]:
                result = result >> effect

            return result

        if node == 'effect.then':
            condition = self._effect_input(
                raw,
                'effect',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            then = self._effect_input(
                raw,
                'then',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            else_effect = self._optional_effect(
                raw.get('else'),
                path=f"{path}.else",
                depth=depth + 1,
                allow_target=allow_target,
            )
            return condition.to(then, else_=else_effect)

        if node == 'effect.if':
            condition = self._condition(
                raw['condition'],
                path=f"{path}.condition",
                depth=depth + 1,
                allow_target=allow_target,
            )
            then = self._effect_input(
                raw,
                'then',
                path=path,
                depth=depth,
                allow_target=allow_target,
            )
            else_effect = self._optional_effect(
                raw.get('else'),
                path=f"{path}.else",
                depth=depth + 1,
                allow_target=allow_target,
            )
            return Check(condition).to(then, else_=else_effect)

        if node == 'effect.for':
            count = self._literal_count(
                raw['count'],
                path=f"{path}.count",
                depth=depth + 1,
            )
            index_name = raw.get('indexVariable')
            index_variable = None

            if index_name is None:
                effect = self._effect_input(
                    raw,
                    'effect',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                )
            else:
                with self._scoped_variable(
                    index_name,
                    int,
                    path=f"{path}.indexVariable",
                    node_id=node_id,
                ) as index_variable:
                    effect = self._effect_input(
                        raw,
                        'effect',
                        path=path,
                        depth=depth,
                        allow_target=allow_target,
                    )

            return For(
                count=count,
                effect=effect,
                index_var=index_variable,
            )

        if node == 'effect.for_each':
            iterable, variable_type = self._iterable(
                raw['iterable'],
                path=f"{path}.iterable",
                depth=depth + 1,
                allow_target=allow_target,
            )
            variable_name = raw.get('variable')
            index_name = raw.get('indexVariable')

            if index_name is not None and index_name == variable_name:
                self._fail(
                    'DUPLICATE_SCOPED_VARIABLE',
                    "The item and index variables must have different names.",
                    path=f"{path}.indexVariable",
                    node_id=node_id,
                )

            with ExitStack() as stack:
                variable = stack.enter_context(self._scoped_variable(
                    variable_name,
                    variable_type,
                    path=f"{path}.variable",
                    node_id=node_id,
                ))

                index_variable = None
                if index_name is not None:
                    index_variable = stack.enter_context(self._scoped_variable(
                        index_name,
                        int,
                        path=f"{path}.indexVariable",
                        node_id=node_id,
                    ))

                effect = self._effect_input(
                    raw,
                    'effect',
                    path=path,
                    depth=depth,
                    allow_target=allow_target,
                )

            return ForEach(
                iterable=iterable,
                effect=effect,
                var=variable,
                index_var=index_variable,
            )

        if node in _ACTIONS:
            return self._action(
                node,
                raw,
                path=path,
                depth=depth,
                node_id=node_id,
                allow_target=allow_target,
            )

        self._fail(
            'UNKNOWN_EFFECT_NODE',
            f"Unsupported effect node {node!r}.",
            path=path,
            node_id=node_id,
        )

    def _compile_variables(
        self,
        raw_variables: list,
        *,
        path: str,
    ) -> None:
        if len(raw_variables) > self.validation.limits.max_variables_per_entity:
            self._fail(
                'TOO_MANY_VARIABLES',
                (
                    "An entity may declare at most "
                    f"{self.validation.limits.max_variables_per_entity} variables."
                ),
                path=path,
            )

        variable_types = {
            'selector': TargetSelector,
            'integer': int,
            'boolean': bool,
            'result': StepResult,
        }

        for index, raw_variable in enumerate(raw_variables):
            variable_path = f"{path}[{index}]"
            if type(raw_variable) is not dict:
                self._fail(
                    'INVALID_VARIABLE',
                    "Each variable declaration must be an object.",
                    path=variable_path,
                )

            node_id = self._node_id(raw_variable, path=variable_path)
            name = raw_variable.get('name')

            if type(name) is not str or _VARIABLE_NAME.fullmatch(name) is None:
                self._fail(
                    'INVALID_VARIABLE_NAME',
                    (
                        "Variable names must contain at most 64 letters, "
                        "numbers, or underscores and cannot begin with a number."
                    ),
                    path=f"{variable_path}.name",
                    node_id=node_id,
                )

            if name in self.variables:
                self._fail(
                    'DUPLICATE_VARIABLE',
                    f"Variable {name!r} is declared more than once.",
                    path=f"{variable_path}.name",
                    node_id=node_id,
                )

            type_name = raw_variable.get('type')
            variable_type = variable_types.get(type_name)
            if variable_type is None:
                self._fail(
                    'INVALID_VARIABLE_TYPE',
                    f"Unknown variable type {type_name!r}.",
                    path=f"{variable_path}.type",
                    node_id=node_id,
                )

            variable = Var(variable_type)
            variable.name = f'_scripted_variable_{index}'
            self.variables[name] = variable

    def _compile_abilities(
        self,
        raw_abilities: list,
        *,
        path: str,
        target_available: bool,
    ) -> dict[Ability, Any]:
        abilities = {}
        seen = set()

        for index, raw_ability in enumerate(raw_abilities):
            ability_path = f"{path}[{index}]"
            if type(raw_ability) is not dict:
                self._fail(
                    'INVALID_ABILITY',
                    "Each ability declaration must be an object.",
                    path=ability_path,
                )

            node_id = self._node_id(raw_ability, path=ability_path)
            ability_name = raw_ability.get('ability')

            if type(ability_name) is not str:
                self._fail(
                    'UNKNOWN_ABILITY',
                    "An ability name must be a string.",
                    path=f"{ability_path}.ability",
                    node_id=node_id,
                )

            if ability_name in seen:
                self._fail(
                    'DUPLICATE_ABILITY',
                    f"Ability {ability_name!r} is declared more than once.",
                    path=f"{ability_path}.ability",
                    node_id=node_id,
                )

            seen.add(ability_name)

            try:
                ability = Ability(ability_name)
            except ValueError:
                self._fail(
                    'UNKNOWN_ABILITY',
                    f"Unsupported ability {ability_name!r}.",
                    path=f"{ability_path}.ability",
                    node_id=node_id,
                )

            if ability not in _ALLOWED_ABILITIES[self.entity.kind]:
                self._fail(
                    'ABILITY_NOT_ALLOWED',
                    f"{ability_name!r} is not available to {self.entity.kind} scripted content.",
                    path=f"{ability_path}.ability",
                    node_id=node_id,
                )

            abilities[ability] = self._effect(
                raw_ability['effect'],
                path=f"{ability_path}.effect",
                depth=1,
                allow_target=(
                    target_available
                    and ability in (
                        Ability.MAGIC,
                        Ability.SYNERGY,
                        Ability.DELAY,
                        Ability.SHOCK,
                    )
                ),
            )

        return abilities

    def _compile_reactions(
        self,
        raw_reactions: list,
        *,
        path: str,
    ) -> tuple[CompiledReaction, ...]:
        reactions = []

        for index, raw_reaction in enumerate(raw_reactions):
            reaction_path = f"{path}[{index}]"
            if type(raw_reaction) is not dict:
                self._fail(
                    'INVALID_REACTION',
                    "Each reaction declaration must be an object.",
                    path=reaction_path,
                )

            node_id = self._node_id(raw_reaction, path=reaction_path)
            event_name = raw_reaction.get('event')
            spec = _EVENTS.get(event_name)
            if spec is None:
                self._fail(
                    'UNKNOWN_REACTION_EVENT',
                    f"Unsupported event reaction {event_name!r}.",
                    path=f"{reaction_path}.event",
                    node_id=node_id,
                )

            previous_event = self.event_name
            self.event_name = event_name

            try:
                raw_condition = raw_reaction['condition']
                condition = (
                    True
                    if raw_condition is None
                    else self._condition(
                        raw_condition,
                        path=f"{reaction_path}.condition",
                        depth=1,
                        allow_target=False,
                    )
                )
                effect = self._effect(
                    raw_reaction['effect'],
                    path=f"{reaction_path}.effect",
                    depth=1,
                    allow_target=False,
                )
            finally:
                self.event_name = previous_event

            reactions.append(
                CompiledReaction(
                    result_type=spec.result_type,
                    condition=condition,
                    effect=effect,
                )
            )

        return tuple(reactions)

    def compile(self) -> CompiledProgram | None:
        raw = self.entity.implementation
        path = f"{self.entity.path}.implementation"

        try:
            if type(raw) is not dict:
                self._fail(
                    'INVALID_IMPLEMENTATION',
                    "An implementation must be an object.",
                    path=path,
                )

            if raw['irVersion'] != 1:
                self._fail(
                    'UNSUPPORTED_IR_VERSION',
                    "Only semantic IR version 1 is supported.",
                    path=f"{path}.irVersion",
                )

            raw_variables = raw['variables']
            if type(raw_variables) is not list:
                self._fail(
                    'INVALID_VARIABLES',
                    "variables must be an array.",
                    path=f"{path}.variables",
                )

            self._compile_variables(
                raw_variables,
                path=f"{path}.variables",
            )

            targets = None
            if raw['targets'] is not None:
                if self.entity.kind not in ('monster', 'spell'):
                    self._fail(
                        'TARGETS_NOT_ALLOWED',
                        "Only Monsters and Spells may declare on-play targets.",
                        path=f"{path}.targets",
                    )

                targets = self._selector(
                    raw['targets'],
                    path=f"{path}.targets",
                    depth=1,
                    allow_target=False,
                )

            need = None
            if raw['need'] is not None:
                if self.entity.kind != 'monster':
                    self._fail(
                        'NEED_NOT_ALLOWED',
                        "Only Monsters may declare Need.",
                        path=f"{path}.need",
                    )

                need = self._condition(
                    raw['need'],
                    path=f"{path}.need",
                    depth=1,
                    allow_target=False,
                )

            raw_abilities = raw['abilities']
            if type(raw_abilities) is not list:
                self._fail(
                    'INVALID_ABILITIES',
                    "abilities must be an array.",
                    path=f"{path}.abilities",
                )

            raw_reactions = raw['reactions']
            if type(raw_reactions) is not list:
                self._fail(
                    'INVALID_REACTIONS',
                    "reactions must be an array.",
                    path=f"{path}.reactions",
                )

            abilities = self._compile_abilities(
                raw_abilities,
                path=f"{path}.abilities",
                target_available=targets is not None,
            )
            reactions = self._compile_reactions(
                raw_reactions,
                path=f"{path}.reactions",
            )

            return CompiledProgram(
                targets=targets,
                need=need,
                abilities=abilities,
                variables=self.variables,
                reactions=reactions,
            )

        except _CompileAbort:
            return None

        except KeyError as exc:
            self.validation.error(
                'MISSING_IR_FIELD',
                f"Missing required field {exc.args[0]!r}.",
                path=path,
                entity_id=self.entity.content_id,
            )
            return None


def compile_program(
    entity: ParsedEntity,
    *,
    base: ContentCatalog,
    entities: list[ParsedEntity],
    validation: ValidationContext,
    budget: NodeBudget,
) -> CompiledProgram | None:
    return IRCompiler(
        entity,
        base=base,
        entities=entities,
        validation=validation,
        budget=budget,
    ).compile()
