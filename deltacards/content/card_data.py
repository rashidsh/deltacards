import hashlib
import json
from pathlib import Path
from typing import Any

from deltacards.model.enums import (
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardToggleableAbility,
    CardType,
    Expansion,
    Tribe,
)

CARD_CACHE_VERSION = 2

KEYWORD_MAP = {
    'charge': CardKeyword.CHARGE.name,
    'haste': CardKeyword.HASTE.name,
    'taunt': CardKeyword.TAUNT.name,
    'kr': CardKeyword.KR.name,
    'candy': CardKeyword.CANDY.name,
    'armor': CardKeyword.ARMOR.name,
    'transparency': CardKeyword.TRANSPARENCY.name,
    'disarmed': CardKeyword.DISARMED.name,
    'invulnerable': CardKeyword.INVULNERABLE.name,
    'wanted': CardKeyword.WANTED.name,
    'darkspawn': CardKeyword.DARKSPAWN.name,
    'flowerypower': CardKeyword.FLOWERY_POWER.name,
}

STATUS_MAP = {
    'paralyzed': CardStatusId.PARALYZED.name,
    'dodge': CardStatusId.DODGE.name,
    'loop': CardStatusId.LOOP.name,
}

TOGGLEABLE_ABILITY_MAP = {
    'shock': CardToggleableAbility.SHOCK.name,
    'support': CardToggleableAbility.SUPPORT.name,
    'bullseye': CardToggleableAbility.BULLSEYE.name,
    'program': CardToggleableAbility.PROGRAM.name,
}


NAME_OVERRIDES = {
    270: "Thrashing Machine",
}


def _calculate_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def convert_card(d: dict[str, Any], abilities_by_card: dict[int, set[str]]) -> dict[str, Any]:
    card_id = d['fixedId']

    keywords = set()
    statuses = {}
    active_abilities = set()

    for status in d['statuses']:
        status_name = status['name'].lower()

        if status_name in KEYWORD_MAP:
            keywords.add(KEYWORD_MAP[status_name])
        elif status_name in STATUS_MAP:
            statuses[STATUS_MAP[status_name]] = int(status['counter'])
        elif status_name in TOGGLEABLE_ABILITY_MAP:
            active_abilities.add(TOGGLEABLE_ABILITY_MAP[status_name])
        else:
            raise ValueError(f"Unknown source status {status_name} on card {card_id}")

    record = dict(
        id=card_id,
        type=CardType(d['typeCard']).name,
        name=NAME_OVERRIDES.get(card_id, d['name']),
        image=d['image'],
        rarity=CardRarity[d['rarity']].name,
        cost=d['cost'],
        abilities=sorted(abilities_by_card.get(card_id, set())),
        keywords=sorted(keywords),
        statuses=dict(sorted(statuses.items())),
        active_abilities=sorted(active_abilities),
        expansion=Expansion(d['extension'].lower()).name,
        tribes=tuple(
            Tribe(tribe_id.lower()).name
            for tribe_id in d['tribes']
        ),
        soul_id=d['soul']['name'].lower() if d.get('soul') else None,
    )

    match d['typeCard']:
        case CardType.MONSTER.value:
            record.update(dict(
                attack=int(d['attack']),
                hp=int(d['hp']),
            ))
        case CardType.SPELL.value:
            pass
        case _:
            raise ValueError(f"Unknown card type {d['typeCard']} on card {card_id}")

    return record


def convert_cards(source_cards: list[dict], abilities_by_card: dict[int, set[str]]):
    if not isinstance(source_cards, list):
        raise ValueError("AllCards.json must contain a JSON array")

    records = []
    seen_ids = set()

    for source_card in source_cards:
        if not isinstance(source_card, dict):
            raise ValueError("AllCards.json contains a non-object card entry")

        record = convert_card(source_card, abilities_by_card)
        card_id = record['id']

        if card_id in seen_ids:
            raise ValueError(f"Duplicate card ID {card_id}")

        seen_ids.add(card_id)
        records.append(record)

    return sorted(records, key=lambda r: r['id'])


def _read_cache(path: Path, *, source_hash: str, abilities_hash: str) -> list[dict[str, Any]] | None:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cards_cache = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return None

    metadata = cards_cache['_meta']

    if metadata.get('version') != CARD_CACHE_VERSION:
        return None

    if metadata.get('source_hash') != source_hash:
        return None

    if metadata.get('abilities_hash') != abilities_hash:
        return None

    return cards_cache['cards']


def _write_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_or_build_cards(
    source_path: Path,
    cache_path: Path,
    abilities_by_card: dict[int, set[str]],
    *,
    force_rebuild: bool = False,
) -> list[dict[str, Any]]:
    """
    Load normalized cards from cache, rebuilding the complete cache when any
    input affecting it has changed.
    """
    source_bytes = source_path.read_bytes()
    source_hash = _calculate_hash(source_bytes)

    abilities_hash = _calculate_hash(
        json.dumps(
            {
                str(card_id): sorted(names)
                for card_id, names in sorted(abilities_by_card.items())
            },
            ensure_ascii=False,
        ).encode('utf-8')
    )

    if not force_rebuild:
        cached_cards = _read_cache(
            cache_path,
            source_hash=source_hash,
            abilities_hash=abilities_hash,
        )
        if cached_cards is not None:
            return cached_cards

    source_cards = json.loads(source_bytes)
    if isinstance(source_cards, dict):
        source_cards = json.loads(source_cards['cards'])

    cards = convert_cards(source_cards, abilities_by_card)

    cards_cache = {
        '_meta': {
            'version': CARD_CACHE_VERSION,
            'source_hash': source_hash,
            'abilities_hash': abilities_hash,
        },
        'cards': cards,
    }

    _write_cache(cache_path, cards_cache)
    return cards
