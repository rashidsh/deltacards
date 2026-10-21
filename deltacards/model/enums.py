from enum import Enum, IntEnum, IntFlag


class PlayerId(IntEnum):
    P1 = 1
    P2 = 2

    def opponent(self) -> 'PlayerId':
        return PlayerId.P2 if self is PlayerId.P1 else PlayerId.P1


class CardType(Enum):
    MONSTER = 0
    SPELL = 1


class CardZone(Enum):
    INVALID = 'invalid'
    STACK = 'stack'
    BOARD = 'board'
    HAND = 'hand'
    DECK = 'deck'
    DUSTPILE = 'dustpile'
    ERASED = 'erased'


class CardKeyword(IntFlag):
    NONE = 0
    CHARGE = 1 << 0
    HASTE = 1 << 1
    TAUNT = 1 << 2
    KR = 1 << 3
    CANDY = 1 << 4
    ARMOR = 1 << 5
    TRANSPARENCY = 1 << 6
    DISARMED = 1 << 7
    INVULNERABLE = 1 << 8
    SILENCED = 1 << 9
    WANTED = 1 << 10
    DARKSPAWN = 1 << 11
    FLOWERY_POWER = 1 << 12


class CardStatusId(Enum):
    PARALYZED = 'paralyzed'
    DODGE = 'dodge'
    LOOP = 'loop'
    MOLD_SPORE = 'mold_spore'


class CardToggleableAbility(Enum):
    SHOCK = 'shock'
    SUPPORT = 'support'
    BULLSEYE = 'bullseye'
    PROGRAM = 'program'


class CardRarity(IntEnum):
    BASE = 0
    COMMON = 1
    RARE = 2
    EPIC = 3
    LEGENDARY = 4
    DETERMINATION = 5
    TOKEN = 100
    STORY = 200


class Ability(Enum):
    MAGIC = 'magic'
    SYNERGY = 'synergy'
    DUST = 'dust'
    DELAY = 'delay'
    GAME_START = 'game_start'
    TURN_START = 'turn_start'
    TURN_END = 'turn_end'
    SHOCK = 'shock'
    SUPPORT = 'support'
    TURBO = 'turbo'
    BULLSEYE = 'bullseye'
    PROGRAM = 'program'


class DamageKind(Enum):
    COMBAT = 'combat'
    SPELL = 'spell'
    ABILITY = 'ability'
    FATIGUE = 'fatigue'


class KillCause(Enum):
    COMBAT = 'combat'
    DAMAGE_EFFECT = 'damage_effect'
    DESTROY_EFFECT = 'destroy_effect'
    OTHER = 'other'


class Expansion(Enum):
    BASE = 'base'
    DELTARUNE = 'deltarune'
    UTY = 'uty'


class Tribe(Enum):
    ALL = 'all'
    TEMMIE = 'temmie'
    DOG = 'dog'
    AMALGAMATE = 'amalgamate'
    G_FOLLOWER = 'g_follower'
    LOST_SOUL = 'lost_soul'
    FROGGIT = 'froggit'
    MOLD = 'mold'
    SNAIL = 'snail'
    BOMB = 'bomb'
    PLANT = 'plant'
    ROYAL_GUARD = 'royal_guard'
    CHAOS_WEAPON = 'chaos_weapon'
    PIECE = 'piece'
    ARACHNID = 'arachnid'
    ROYAL_INVENTION = 'royal_invention'
    PLUG = 'plug'
    THRASHING_PART = 'thrashing_part'
    BARGAIN = 'bargain'
    DANCE = 'dance'
    GIGA_ATTACK = 'giga_attack'
    ROUND = 'round'
    PACK = 'pack'
