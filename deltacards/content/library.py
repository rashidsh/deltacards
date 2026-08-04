from typing import Iterable

from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardToggleableAbility,
    CardType,
    Expansion,
    Tribe,
)
from deltacards.model.templates import CardTemplate, MonsterTemplate, SpellTemplate


class CardLibrary:
    def __init__(self):
        self._by_id: dict[int, 'CardTemplate'] = {}
        self._by_name: dict[str, 'CardTemplate'] = {}

    def get(self, fixed_id: int) -> 'CardTemplate':
        return self._by_id[fixed_id]

    def get_by_name(self, name: str) -> 'CardTemplate':
        return self._by_name[name.lower()]

    def _load_template(self, d: dict) -> 'CardTemplate':
        card_id = d['id']

        keywords = CardKeyword.NONE
        for keyword_name in d['keywords']:
            keywords |= CardKeyword[keyword_name]

        statuses = {
            CardStatusId[status_name]: counter
            for status_name, counter in d['statuses'].items()
        }

        active_abilities = set(
            CardToggleableAbility[ability_name]
            for ability_name in d['active_abilities']
        )

        common = dict(
            id=card_id,
            name=d['name'],
            image=d['image'],
            rarity=CardRarity[d['rarity']],
            cost=d['cost'],
            abilities=frozenset(Ability[ability_name] for ability_name in d['abilities']),
            keywords=keywords,
            statuses=statuses,
            active_abilities=active_abilities,
            expansion=Expansion[d['expansion']],
            tribes=tuple(Tribe[name] for name in d['tribes']),
            soul_id=d['soul_id'],
        )

        match d['type']:
            case CardType.MONSTER.name:
                return MonsterTemplate(
                    **common,
                    attack=d['attack'],
                    hp=d['hp'],
                )
            case CardType.SPELL.name:
                return SpellTemplate(**common)
            case _:
                raise ValueError("Invalid card type")

    def set_templates(self, templates: Iterable[CardTemplate]) -> None:
        by_id = {}
        by_name = {}

        for template in templates:
            if template.id in by_id:
                raise ValueError(f"Duplicate card ID {template.id}")

            template_name = template.name.lower()
            if template_name in by_name:
                raise ValueError(f"Duplicate card name {template.name}")

            by_id[template.id] = template
            by_name[template_name] = template

        self._by_id = by_id
        self._by_name = by_name

    def load_templates(self, data: list[dict]) -> None:
        self.set_templates(
            self._load_template(d)
            for d in data
        )


LIBRARY = CardLibrary()
