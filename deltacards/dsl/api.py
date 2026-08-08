from deltacards.actions import results as _action_results
from deltacards.actions import standard as _action_standard
from deltacards.engine import modifiers as _modifiers

from deltacards.actions.results import *
from deltacards.actions.standard import *
from deltacards.engine.modifiers import *

from deltacards.engine.constants import MAX_HAND_SIZE
from deltacards.engine.effects import (
    Check,
    For,
    ForEach,
    NoEffect,
    StepResult,
    While,
)
from deltacards.model.artifacts import (
    Artifact,
    ArtifactRarity,
    QuestArtifact,
)
from deltacards.model.enchantments import Enchantment
from deltacards.model.cards import Card, Monster, Spell
from deltacards.model.entity import Entity, on_event
from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardZone,
    DamageKind,
    KillCause,
    Expansion,
    PlayerId,
    Tribe,
)
from deltacards.model.player import Player
from deltacards.model.slots import BoardSlot
from deltacards.model.souls import Soul

from deltacards.content.decorators import (
    artifact,
    card,
    enchantment,
    soul,
)
from deltacards.content.registry import (
    CustomImage,
    ExistingImage,
    LocalizedText,
)

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
    AmbiguousTargetError,
    NoTargetsError,
    Predicate,
    TargetSelector,
    TargetingError,
    Transform,
    ValueExpr,
)
from deltacards.dsl.discovery import DISCOVER
from deltacards.dsl.history import (
    ABILITY_TRIGGERS,
    AMOUNT,
    ANOTHER_SOUL_THAN,
    ATTACKER_ID,
    ATTACKS_DECLARED,
    ATTACKS_RESOLVED,
    CARD_ID,
    CARD_SOUL,
    CARDS_DRAWN,
    CARDS_PLAYED,
    DEFENDER_ID,
    GOLD_SPENT,
    HAS_NEED_CONDITION,
    HEALED_AMOUNT,
    HEALING_DONE,
    IN_HISTORY,
    IS_COMBAT_KILL,
    KILL_CAUSE,
    KILLED_BY_MONSTER,
    LAST_TURN_OF,
    MONSTER_ID,
    MONSTERS_DIED,
    NEED_FULFILLED,
    OF_SOUL,
    PLAYER_SOUL,
    REASON,
    SPELLS_CAST,
    SPENT_GOLD_AMOUNT,
    SPENT_GOLD_LAST_TURN,
    SPENT_GOLD_LAST_TURN_OF,
    SPENT_GOLD_LAST_TURN_ON_SPELLS_OF,
    SPENT_GOLD_ON_SPELLS_LAST_TURN,
    SPENT_GOLD_ON_SPELLS_THIS_TURN,
    SPENT_GOLD_THIS_TURN,
    TEMPLATE_NAME,
    THIS_GAME,
    THIS_TURN,
)
from deltacards.dsl.macros import (
    AddToHandOrDeck,
    DrawUpTo,
    FillBoard,
    FillHand,
    NEXT_LOST_SOUL,
    OncePerTurn,
    Program,
    Switch,
    SwitchPiece,
)
from deltacards.dsl.predicates import (
    DAMAGED,
    DEAD,
    DT,
    HAS_NEGATIVE_EFFECTS,
    EMPTY_SLOT,
    ENCHANTED_SLOT,
    EXPANSION,
    GENERATED,
    GENERATED_BY,
    HAS_ABILITY,
    HAS_ANY_TRIBE,
    HAS_KEYWORD,
    HAS_STATUS,
    HAS_TRIBE,
    IS_CUSTOM_CONTENT,
    IS_MONSTER,
    IS_SPELL,
    NON_DT,
    NON_GENERATED,
    NON_TOKEN,
    OCCUPIED_SLOT,
    SLOT_HAS_ENCHANTMENT,
    TOKEN,
    UNENCHANTED_SLOT,
)
from deltacards.dsl.selectors import (
    ADJACENT,
    ADJACENT_IN_HAND,
    ALLIES,
    ALLY_ENCHANTMENTS,
    ALLY_MONSTERS,
    ALLY_SLOTS,
    ALL_ENCHANTMENTS,
    ALL_SLOTS,
    ARTIFACT_BY_NAME,
    ARTIFACT_OF_PLAYER,
    ATTACKER,
    BOARD,
    BOARD_OF,
    BOARD_SLOTS_OF,
    CARD_BY_NAME,
    CARD_LIBRARY,
    CONTROLLER,
    CONTROLLER_OF,
    DEATH_SLOT,
    DECK,
    DECK_OF,
    DEFENDER,
    DUSTPILE,
    DUSTPILE_OF,
    ENCHANTMENTS_OF,
    ENCHANTMENT_BY_NAME,
    ENCHANTMENT_IN_SLOT,
    ENEMIES,
    ENEMY_ENCHANTMENTS,
    ENEMY_MONSTERS,
    ENEMY_SLOTS,
    ERASED,
    ERASED_OF,
    FRONT,
    HAND,
    HAND_OF,
    KILLER,
    LEFT,
    LEFT_IN_HAND,
    LEFT_OF,
    LEFT_OF_HAND,
    ALL_MONSTERS,
    LOOP_COPY,
    MONSTER_IN_SLOT,
    OPPONENT,
    OPPONENT_BOARD,
    OPPONENT_DECK,
    OPPONENT_DUSTPILE,
    OPPONENT_ERASED,
    OPPONENT_HAND,
    OPPONENT_OF,
    ALL_PLAYERS,
    RANGE,
    RESOLVE_ENTITY,
    RIGHT,
    RIGHT_IN_HAND,
    RIGHT_OF_HAND,
    RIGHT_OF,
    SELF,
    SLOT_OF,
    THIS_SLOT_MONSTER,
    TRIGGER_CARD,
    TARGET,
    TURN_PLAYER,
    YOU,
)
from deltacards.dsl.transforms import (
    AS_CARDS,
    AS_TEMPLATES,
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
    WEIGHTED_RANDOM,
)
from deltacards.dsl.values import (
    ATTACK,
    BASE_ATTACK,
    BASE_COST,
    BASE_HP,
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
)
from deltacards.dsl.vars import CHOICE_NOT_SELECTED, CHOICE_SELECTED, StateVar, VAR, Var
from deltacards.model.templates import CardTemplate, MonsterTemplate, SpellTemplate

# Card keywords
CHARGE = CardKeyword.CHARGE
HASTE = CardKeyword.HASTE
TAUNT = CardKeyword.TAUNT
KR = CardKeyword.KR
CANDY = CardKeyword.CANDY
ARMOR = CardKeyword.ARMOR
TRANSPARENCY = CardKeyword.TRANSPARENCY
DISARMED = CardKeyword.DISARMED
INVULNERABLE = CardKeyword.INVULNERABLE
SILENCED = CardKeyword.SILENCED
WANTED = CardKeyword.WANTED
DARKSPAWN = CardKeyword.DARKSPAWN
FLOWERY_POWER = CardKeyword.FLOWERY_POWER

# Card statuses
PARALYZED = CardStatusId.PARALYZED
DODGE = CardStatusId.DODGE
LOOP = CardStatusId.LOOP

# Card rarities
BASE = CardRarity.BASE
COMMON = CardRarity.COMMON
RARE = CardRarity.RARE
EPIC = CardRarity.EPIC
LEGENDARY = CardRarity.LEGENDARY

# Abilities
MAGIC = Ability.MAGIC
SYNERGY = Ability.SYNERGY
DUST = Ability.DUST
DELAY = Ability.DELAY
TURN_START = Ability.TURN_START
TURN_END = Ability.TURN_END
SHOCK = Ability.SHOCK
SUPPORT = Ability.SUPPORT
TURBO = Ability.TURBO
BULLSEYE = Ability.BULLSEYE
PROGRAM = Ability.PROGRAM

NO_EFFECT = NoEffect()


__all__ = (
    # Constants
    'MAX_HAND_SIZE',

    # Card keywords
    'CHARGE', 'HASTE', 'TAUNT', 'KR', 'CANDY', 'ARMOR', 'TRANSPARENCY', 'DISARMED', 'INVULNERABLE',
    'SILENCED', 'WANTED', 'DARKSPAWN', 'FLOWERY_POWER',

    # Card statuses
    'PARALYZED', 'DODGE', 'LOOP',

    # Card rarities
    'BASE', 'COMMON', 'RARE', 'EPIC', 'LEGENDARY',

    # Abilities
    'MAGIC', 'SYNERGY', 'DUST', 'DELAY', 'TURN_START', 'TURN_END',
    'SHOCK', 'SUPPORT', 'TURBO', 'BULLSEYE', 'PROGRAM',

    # Core
    'TargetSelector',
    'Predicate',
    'Transform',
    'ValueExpr',
    'TargetingError',
    'NoTargetsError',
    'AmbiguousTargetError',

    # Aggregates
    'COUNT',
    'COUNT_DISTINCT',
    'COUNT_UNIQUE_TRIBES',
    'EXISTS',
    'MAXVAL',
    'MINVAL',
    'SUM',
    'UNIQUE_TRIBES',
    'UNIQUE_VALUES',

    # Selectors
    'SELF', 'TARGET', 'KILLER', 'ATTACKER', 'DEFENDER', 'LOOP_COPY', 'TRIGGER_CARD', 'DEATH_SLOT',
    'YOU', 'CONTROLLER', 'OPPONENT', 'TURN_PLAYER', 'ALL_PLAYERS',

    'RESOLVE_ENTITY',

    'RANGE',

    'BOARD', 'HAND', 'DECK', 'DUSTPILE', 'ERASED',
    'OPPONENT_BOARD', 'OPPONENT_HAND', 'OPPONENT_DECK', 'OPPONENT_DUSTPILE', 'OPPONENT_ERASED',

    'ALLY_MONSTERS', 'ENEMY_MONSTERS', 'ALL_MONSTERS',
    'ALLIES', 'ENEMIES',

    'LEFT', 'RIGHT', 'ADJACENT', 'FRONT',
    'LEFT_OF', 'RIGHT_OF',

    'LEFT_IN_HAND', 'RIGHT_IN_HAND', 'ADJACENT_IN_HAND',
    'LEFT_OF_HAND', 'RIGHT_OF_HAND',

    'BOARD_OF', 'HAND_OF', 'DECK_OF', 'DUSTPILE_OF', 'ERASED_OF',
    'CONTROLLER_OF', 'OPPONENT_OF',

    'CARD_LIBRARY', 'CARD_BY_NAME',
    'ARTIFACT_BY_NAME',
    'ARTIFACT_OF_PLAYER',

    'BOARD_SLOTS_OF', 'SLOT_OF', 'MONSTER_IN_SLOT',
    'ALLY_SLOTS', 'ENEMY_SLOTS', 'ALL_SLOTS',
    'THIS_SLOT_MONSTER',

    'ENCHANTMENT_BY_NAME', 'ENCHANTMENTS_OF', 'ENCHANTMENT_IN_SLOT',
    'ALLY_ENCHANTMENTS', 'ENEMY_ENCHANTMENTS', 'ALL_ENCHANTMENTS',

    # Values
    'ID', 'TEMPLATE_ID',
    'COST', 'RARITY',
    'ATTACK', 'HP',
    'CREATOR_ID',
    'BASE_COST', 'BASE_ATTACK', 'BASE_HP',
    'EMPTY_SLOTS',
    'CLAMP', 'LEAST', 'GREATEST',
    'SYNERGY_TRIGGERED',
    'HAS_ARTIFACT',

    # Predicates
    'IS_MONSTER',
    'IS_SPELL',
    'DAMAGED',
    'DEAD',
    'HAS_NEGATIVE_EFFECTS',
    'HAS_ABILITY',
    'HAS_KEYWORD',
    'HAS_STATUS',
    'HAS_TRIBE',
    'HAS_ANY_TRIBE',
    'EXPANSION',
    'GENERATED',
    'NON_GENERATED',
    'GENERATED_BY',
    'TOKEN',
    'NON_TOKEN',
    'DT',
    'NON_DT',
    'EMPTY_SLOT',
    'OCCUPIED_SLOT',
    'ENCHANTED_SLOT',
    'UNENCHANTED_SLOT',
    'SLOT_HAS_ENCHANTMENT',
    'IS_CUSTOM_CONTENT',

    # Transforms
    'RANDOM',
    'WEIGHTED_RANDOM',
    'MIN',
    'MAX',
    'LEFTMOST',
    'RIGHTMOST',
    'DISTINCT',
    'SORT_BY',
    'GENERATE_CARD',
    'COPY',
    'EXACT_COPY',
    'AS_TEMPLATES',
    'AS_CARDS',
    'LIMIT_PER',

    # Discovery
    'DISCOVER',

    # Variables
    'Var',
    'StateVar',
    'VAR',
    'CHOICE_SELECTED',
    'CHOICE_NOT_SELECTED',

    # History queries
    'ABILITY_TRIGGERS',
    'AMOUNT',
    'ANOTHER_SOUL_THAN',
    'ATTACKER_ID',
    'ATTACKS_DECLARED',
    'ATTACKS_RESOLVED',
    'CARD_ID',
    'CARD_SOUL',
    'CARDS_DRAWN',
    'CARDS_PLAYED',
    'DEFENDER_ID',
    'GOLD_SPENT',
    'HAS_NEED_CONDITION',
    'HEALED_AMOUNT',
    'HEALING_DONE',
    'IN_HISTORY',
    'IS_COMBAT_KILL',
    'KILL_CAUSE',
    'KILLED_BY_MONSTER',
    'LAST_TURN_OF',
    'MONSTER_ID',
    'MONSTERS_DIED',
    'NEED_FULFILLED',
    'OF_SOUL',
    'PLAYER_SOUL',
    'REASON',
    'SPELLS_CAST',
    'SPENT_GOLD_AMOUNT',
    'SPENT_GOLD_LAST_TURN',
    'SPENT_GOLD_LAST_TURN_OF',
    'SPENT_GOLD_LAST_TURN_ON_SPELLS_OF',
    'SPENT_GOLD_ON_SPELLS_LAST_TURN',
    'SPENT_GOLD_ON_SPELLS_THIS_TURN',
    'SPENT_GOLD_THIS_TURN',
    'TEMPLATE_NAME',
    'THIS_GAME',
    'THIS_TURN',

    # Macros
    'Program',
    'Switch',
    'SwitchPiece',
    'DrawUpTo',
    'FillBoard',
    'FillHand',
    'AddToHandOrDeck',
    'OncePerTurn',

    'NEXT_LOST_SOUL',

    # Effects
    'Check', 'For', 'ForEach', 'While', 'StepResult',
    'NO_EFFECT',

    # Content definitions
    'ExistingImage',
    'CustomImage',
    'LocalizedText',

    # Cards
    'Card', 'Monster', 'Spell', 'card',

    # Templates
    'CardTemplate',
    'MonsterTemplate',
    'SpellTemplate',

    # Artifacts
    'Artifact',
    'ArtifactRarity',
    'QuestArtifact',
    'artifact',

    # Souls
    'Soul',
    'soul',

    # Enchantments
    'Enchantment', 'enchantment',

    # Board slots
    'BoardSlot',

    # Entity
    'Entity', 'on_event',

    # Players
    'Player',

    # Enums
    'Ability',
    'CardKeyword',
    'CardRarity',
    'CardStatusId',
    'CardZone',
    'DamageKind',
    'KillCause',
    'Expansion',
    'PlayerId',
    'Tribe',

    *_action_results.__all__,
    *_action_standard.__all__,
    *_modifiers.__all__,
)
