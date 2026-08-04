from deltacards.content.library import LIBRARY
from deltacards.model.cards import (
    Card,
    Monster,
    Spell,
    card as register_card,
)
from deltacards.model.enums import (
    Ability,
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardToggleableAbility,
    Expansion,
    Tribe,
)
from deltacards.model.templates import (
    CardTemplate,
    MonsterTemplate,
    SpellTemplate,
)


TEST_CARD_TEMPLATES: dict[int, CardTemplate] = {}


def add_test_template(template: CardTemplate) -> None:
    if template.id in TEST_CARD_TEMPLATES:
        raise ValueError(f"Duplicate test card template ID {template.id}")

    TEST_CARD_TEMPLATES[template.id] = template


def synthetic_card(
    template_id: int,
    *,
    cost: int,
    attack: int | None = None,
    hp: int | None = None,
    name: str | None = None,
    rarity: CardRarity = CardRarity.BASE,
    keywords: CardKeyword = CardKeyword.NONE,
    statuses: dict[CardStatusId, int] | None = None,
    active_abilities: set[CardToggleableAbility] | None = None,
    expansion: Expansion = Expansion.BASE,
    tribes: tuple[Tribe, ...] = (),
    soul_id: str | None = None,
):
    def wrapper(class_: type[Card]) -> type[Card]:
        if template_id in TEST_CARD_TEMPLATES:
            raise ValueError(f"Duplicate test card template ID {template_id}")

        common = dict(
            id=template_id,
            name=name or class_.__name__,
            image=name,
            rarity=rarity,
            cost=cost,
            abilities=frozenset(
                Ability[ability_name]
                for ability_name in class_.declared_ability_names()
            ),
            keywords=keywords,
            statuses=dict(statuses or {}),
            active_abilities=set(active_abilities or ()),
            expansion=expansion,
            tribes=tribes,
            soul_id=soul_id,
        )

        if issubclass(class_, Monster):
            if (attack is None) or (hp is None):
                raise ValueError(f"Synthetic Monster {template_id} must declare attack and HP")

            template = MonsterTemplate(
                **common,
                attack=attack,
                hp=hp,
            )

        elif issubclass(class_, Spell):
            if (attack is not None) or (hp is not None):
                raise ValueError(f"Synthetic Spell {template_id} cannot declare attack or HP")

            template = SpellTemplate(**common)

        else:
            raise TypeError(f"Synthetic card {template_id} must inherit Monster or Spell")

        register_card(template_id)(class_)
        TEST_CARD_TEMPLATES[template_id] = template
        return class_

    return wrapper


def load_test_templates() -> None:
    LIBRARY.set_templates(TEST_CARD_TEMPLATES.values())


# Dummy is defined here as it is the default test "filler" card
add_test_template(
    MonsterTemplate(
        id=1,
        name="Dummy",
        image="Dummy",
        rarity=CardRarity.BASE,
        cost=1,
        abilities=frozenset(),
        keywords=CardKeyword.NONE,
        statuses={},
        active_abilities=set(),
        expansion=Expansion.BASE,
        tribes=(),
        soul_id=None,
        attack=0,
        hp=4,
    )
)
