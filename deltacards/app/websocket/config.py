from dataclasses import dataclass, field


DEFAULT_HUMAN_USERNAME = "Player"
DEFAULT_BOT_USERNAME = "CPU (simple)"
DEFAULT_PLAYER_LEVEL = 1

DEFAULT_GAME_TYPE = 'CPU'
DEFAULT_RANK = 'COPPER_III'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8080

WAIT_TIMES = {
    'MONSTER_PLAY_WAIT': 0.3,
    'SPELL_PLAY_WAIT': 0.8,
    'SHOW_CARD_WAIT': 1.0,
    'OVERDRAW_WAIT': 1.0,
    'EFFECT_WAIT': 0.3,
    'COMBAT_WAIT': 0.5,

    'BIG_DAMAGE': 0.3,
    'BLACK_OUT': 0.7,
    'SAVE': 0.0,
    'LOAD': 0.0,
    'BARRIER_BREAK': 3.0,
    'SILENCE': 0.5,
    'SPELL': 0.0,
    'ATTACK_BUFF': 0.1,
    'HP_BUFF': 0.1,
    'ATTACK_DEBUFF': 0.1,
    'HP_DEBUFF': 0.1,
    'FREEZE': 0.25,
    'POISON': 0.25,
    'HEAL': 0.25,
    'HP_STAT': 0.0,
    'COST_STAT': 0.0,
    'ATTACK_STAT': 0.0,
}


@dataclass(frozen=True, slots=True)
class AssetConfig:
    avatar_image: str = 'Dummy'
    avatar_rarity: str = 'BASE'

    profile_skin_name: str = 'Base'
    profile_skin_image: str = 'Base'

    default_emote_id: str = 'wave'
    default_emote_image: str = 'wave'

    frame_skin_name: str = 'undertale'


@dataclass(frozen=True, slots=True)
class PresentationConfig:
    emit_animation_events: bool = True
    wait_times_enabled: bool = True
    wait_times: dict[str, float] = field(default_factory=lambda: WAIT_TIMES.copy())

    def wait_time(self, name: str) -> float:
        if not self.wait_times_enabled:
            return 0.0

        return float(self.wait_times.get(name, 0.0))


@dataclass(frozen=True, slots=True)
class ServerConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    assets: AssetConfig = field(default_factory=AssetConfig)
    presentation: PresentationConfig = field(default_factory=PresentationConfig)

    human_deck_name: str | None = None
    bot_deck_name: str | None = None

    game_seed_base: int | None = None
    max_message_size: int = 1024 * 1024
    battle_log_limit: int = 250
