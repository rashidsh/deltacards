import inspect
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deltacards.model.artifacts import (
    Artifact,
    ArtifactRarity,
    QuestArtifact,
)
from deltacards.model.cards import (
    Card,
    Monster,
    Spell,
)
from deltacards.model.enchantments import (
    Enchantment,
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
from deltacards.model.souls import (
    Soul,
)
from deltacards.model.templates import (
    CardTemplate,
    MonsterTemplate,
    SpellTemplate,
)
from .registration import ContentRegistration, attach_registration
from .registry import (
    ContentPresentation,
    ImageSpec,
    LocalizedText,
)


_TOGGLEABLE_ABILITIES = {
    Ability.SHOCK: CardToggleableAbility.SHOCK,
    Ability.SUPPORT: CardToggleableAbility.SUPPORT,
    Ability.BULLSEYE: CardToggleableAbility.BULLSEYE,
    Ability.PROGRAM: CardToggleableAbility.PROGRAM,
}


def _source_directory(class_: type) -> Path:
    return Path(inspect.getfile(class_)).resolve().parent


def _localizations(
    *,
    name: str,
    description: str,
    localizations: Mapping[str, LocalizedText] | None,
) -> dict[str, LocalizedText]:
    result = {
        'en': LocalizedText(
            name=name,
            description=description,
        ),
    }

    if localizations is not None:
        result.update({
            locale: LocalizedText(
                name=localization.name,
                description=(
                    localization.description
                    if localization.description is not None
                    else description
                ),
            )
            for locale, localization in localizations.items()
        })

    return result


def _presentation(
    *,
    class_: type,
    kind: str,
    content_id: int | str,
    name: str,
    description: str,
    image: ImageSpec,
    localizations: Mapping[str, LocalizedText] | None,
    overlay: ImageSpec = None,
    log: ImageSpec = None,
) -> ContentPresentation:
    return ContentPresentation(
        kind=kind,
        content_id=content_id,
        localizations=_localizations(
            name=name,
            description=description,
            localizations=localizations,
        ),
        image=image,
        source_directory=_source_directory(class_),
        overlay=overlay,
        log=log,
    )


def _declared_abilities(class_: type[Card]) -> frozenset[Ability]:
    return frozenset(
        Ability[name]
        for name in class_.declared_ability_names()
    )


def _initial_active_abilities(
    *,
    declared_abilities: frozenset[Ability],
    active_abilities: set[CardToggleableAbility] | None,
) -> frozenset[CardToggleableAbility]:
    if active_abilities is not None:
        return frozenset(active_abilities)

    # A Python-authored Shock, Support, Bullseye, or Program ability should
    # be usable by default. Passing an explicit empty set opts out.
    return frozenset({
        toggleable
        for ability, toggleable in _TOGGLEABLE_ABILITIES.items()
        if ability in declared_abilities
    })


def _attach(
    class_: type,
    *,
    kind: str,
    content_id: int | str,
    template: CardTemplate | None = None,
    presentation: ContentPresentation | None = None,
):
    return attach_registration(
        class_,
        ContentRegistration(
            kind=kind,
            content_id=content_id,
            implementation=class_,
            template=template,
            presentation=presentation,
        ),
    )


def _register_card(card_id: int):
    def wrapper(class_: type[Card]) -> type[Card]:
        if not issubclass(class_, Card):
            raise TypeError("A card definition must inherit Card")

        return _attach(
            class_,
            kind='card',
            content_id=card_id,
        )

    return wrapper


def _define_card(
    card_id: int,
    *,
    name: str,
    cost: int,
    description: str = '',
    rarity: CardRarity = CardRarity.COMMON,
    attack: int | None = None,
    hp: int | None = None,
    keywords: CardKeyword = CardKeyword.NONE,
    statuses: Mapping[CardStatusId, int] | None = None,
    active_abilities: set[CardToggleableAbility] | None = None,
    expansion: Expansion = Expansion.BASE,
    tribes: Sequence[Tribe] = (),
    soul_id: str | None = None,
    image: ImageSpec = None,
    localizations: Mapping[str, LocalizedText] | None = None,
):
    def wrapper(class_: type[Card]) -> type[Card]:
        declared_abilities = _declared_abilities(class_)
        initial_active_abilities = _initial_active_abilities(
            declared_abilities=declared_abilities,
            active_abilities=active_abilities,
        )

        common = {
            'id': card_id,
            'name': name,
            'image': image,
            'rarity': rarity,
            'cost': cost,
            'abilities': declared_abilities,
            'keywords': keywords,
            'statuses': dict(statuses or {}),
            'active_abilities': initial_active_abilities,
            'expansion': expansion,
            'tribes': tuple(tribes),
            'soul_id': soul_id,
        }

        if issubclass(class_, Monster):
            if (attack is None) or (hp is None):
                raise ValueError(f"Monster {card_id} must declare attack and HP")

            template = MonsterTemplate(
                **common,
                attack=attack,
                hp=hp,
            )

        elif issubclass(class_, Spell):
            if (attack is not None) or (hp is not None):
                raise ValueError(f"Spell {card_id} cannot declare attack or HP")

            template = SpellTemplate(**common)

        else:
            raise TypeError(f"A card definition must inherit Monster or Spell")

        presentation = _presentation(
            class_=class_,
            kind='card',
            content_id=card_id,
            name=name,
            description=description,
            image=image,
            localizations=localizations,
        )

        return _attach(
            class_,
            kind='card',
            content_id=card_id,
            template=template,
            presentation=presentation,
        )

    return wrapper


def card(
    card_id: int,
    **definition: Any,
):
    """
    With no keyword arguments, associate behavior with a template present in AllCards.json.
    With keyword arguments, define a complete Python-authored card.
    """
    if not definition:
        return _register_card(card_id)

    return _define_card(card_id, **definition)


def _register_artifact(artifact_id: int):
    def wrapper(class_: type[Artifact]) -> type[Artifact]:
        if not issubclass(class_, Artifact):
            raise TypeError("An Artifact definition must inherit Artifact")

        class_.definition_id = artifact_id
        return _attach(
            class_,
            kind='artifact',
            content_id=artifact_id,
        )

    return wrapper


def _define_artifact(
    artifact_id: int,
    *,
    name: str,
    description: str = '',
    rarity: ArtifactRarity = ArtifactRarity.COMMON,
    initial_counter: int = 0,
    image: ImageSpec = None,
    overlay: ImageSpec = None,
    localizations: Mapping[str, LocalizedText] | None = None,
    quest_goal: int | None = None,
):
    def wrapper(class_: type[Artifact]) -> type[Artifact]:
        if not issubclass(class_, Artifact):
            raise TypeError("An Artifact definition must inherit Artifact")

        class_.name = name
        class_.rarity = rarity
        class_.initial_counter = initial_counter

        if issubclass(class_, QuestArtifact):
            goal = (
                quest_goal
                if quest_goal is not None
                else class_.quest_goal
            )
            if goal is None:
                raise ValueError(f"Quest Artifact {artifact_id} must declare quest_goal")

            if overlay is None:
                raise ValueError(f"Quest Artifact {artifact_id} must declare overlay")

            class_.quest_goal = goal

        else:
            if quest_goal is not None:
                raise ValueError(f"Ordinary Artifact {artifact_id} cannot declare quest_goal")

            if overlay is not None:
                raise ValueError(f"Ordinary Artifact {artifact_id} cannot declare overlay")

        class_.definition_id = artifact_id
        presentation = _presentation(
            class_=class_,
            kind='artifact',
            content_id=artifact_id,
            name=name,
            description=description,
            image=image,
            overlay=overlay,
            localizations=localizations,
        )

        return _attach(
            class_,
            kind='artifact',
            content_id=artifact_id,
            presentation=presentation,
        )

    return wrapper


def artifact(
    artifact_id: int,
    **definition: Any,
):
    if not definition:
        return _register_artifact(artifact_id)

    return _define_artifact(artifact_id, **definition)


def _register_soul(soul_id: str):
    def wrapper(class_: type[Soul]) -> type[Soul]:
        if not issubclass(class_, Soul):
            raise TypeError("A Soul definition must inherit Soul")

        class_.definition_id = soul_id
        if 'name' not in class_.__dict__:
            class_.name = class_.__name__.upper()

        return _attach(
            class_,
            kind='soul',
            content_id=soul_id,
        )

    return wrapper


def _define_soul(
    soul_id: str,
    *,
    name: str,
    description: str = '',
    image: ImageSpec = None,
    localizations: Mapping[str, LocalizedText] | None = None,
):
    def wrapper(class_: type[Soul]) -> type[Soul]:
        if not issubclass(class_, Soul):
            raise TypeError("A Soul definition must inherit Soul")

        class_.name = name

        class_.definition_id = soul_id
        presentation = _presentation(
            class_=class_,
            kind='soul',
            content_id=soul_id,
            name=name,
            description=description,
            image=image,
            localizations=localizations,
        )

        return _attach(
            class_,
            kind='soul',
            content_id=soul_id,
            presentation=presentation,
        )

    return wrapper


def soul(
    soul_id: str,
    **definition: Any,
):
    if not definition:
        return _register_soul(soul_id)

    return _define_soul(soul_id, **definition)


def _register_enchantment(enchantment_id: str):
    def wrapper(class_: type[Enchantment]) -> type[Enchantment]:
        if not issubclass(class_, Enchantment):
            raise TypeError("An Enchantment definition must inherit Enchantment")

        class_.definition_id = enchantment_id
        return _attach(
            class_,
            kind='enchantment',
            content_id=enchantment_id,
        )

    return wrapper


def _define_enchantment(
    enchantment_id: str,
    *,
    name: str,
    description: str = '',
    initial_counter: int = 0,
    image: ImageSpec = None,
    overlay: ImageSpec = None,
    log: ImageSpec = None,
    localizations: Mapping[str, LocalizedText] | None = None,
):
    def wrapper(class_: type[Enchantment]) -> type[Enchantment]:
        if not issubclass(class_, Enchantment):
            raise TypeError("An Enchantment definition must inherit Enchantment")

        class_.name = name
        class_.initial_counter = initial_counter

        class_.definition_id = enchantment_id
        presentation = _presentation(
            class_=class_,
            kind='enchantment',
            content_id=enchantment_id,
            name=name,
            description=description,
            image=image,
            overlay=overlay,
            log=log,
            localizations=localizations,
        )

        return _attach(
            class_,
            kind='enchantment',
            content_id=enchantment_id,
            presentation=presentation,
        )

    return wrapper


def enchantment(
    enchantment_id: str,
    **definition: Any,
):
    if not definition:
        return _register_enchantment(enchantment_id)

    return _define_enchantment(enchantment_id, **definition)
