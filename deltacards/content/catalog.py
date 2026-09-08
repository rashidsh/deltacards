from dataclasses import dataclass, replace
from types import ModuleType
from typing import Iterable, Mapping

from deltacards.content.frontend import FrontendContentCatalog
from deltacards.content.library import CardLibrary, normalize_content_name
from deltacards.content.registration import ContentRegistration, registrations_from_module
from deltacards.content.registry import ContentKind, ContentPresentation, ContentRegistry
from deltacards.model.artifacts import Artifact
from deltacards.model.cards import Card
from deltacards.model.enchantments import Enchantment
from deltacards.engine.limits import RuntimeLimits
from deltacards.model.enums import Ability
from deltacards.model.souls import Soul
from deltacards.model.templates import CardTemplate


def _definitions_by_name(
    definitions: Iterable[type],
    *,
    kind: str,
) -> dict[str, type]:
    result = {}

    for definition in definitions:
        name = normalize_content_name(definition.name)
        if name in result:
            raise ValueError(f"Duplicate normalized {kind} name {definition.name!r}")

        result[name] = definition

    return result


@dataclass(slots=True)
class ContentCatalog:
    cards: CardLibrary
    card_implementations: Mapping[int, type[Card]]
    artifacts: Mapping[int, type[Artifact]]
    enchantments: Mapping[str, type[Enchantment]]
    souls: Mapping[str, type[Soul]]

    artifacts_by_name: Mapping[str, type[Artifact]]
    enchantments_by_name: Mapping[str, type[Enchantment]]

    presentation: ContentRegistry
    frontend: FrontendContentCatalog

    source_cards: list[dict]
    runtime_limits: RuntimeLimits | None = None

    def is_custom(self, kind: ContentKind, content_id: int | str) -> bool:
        return self.presentation.is_custom(kind, content_id)

    def artifact_by_name(self, name: str) -> type[Artifact] | None:
        return self.artifacts_by_name.get(normalize_content_name(name))

    def enchantment_by_name(self, name: str) -> type[Enchantment] | None:
        return self.enchantments_by_name.get(normalize_content_name(name))


class ContentBuilder:
    def __init__(
        self,
        *,
        base: ContentCatalog | None = None,
        card_records: Iterable[dict] | None = None,
        card_templates: Iterable[CardTemplate] | None = None,
        source_cards: Iterable[dict] | None = None,
    ):
        if base is not None:
            if (card_records is not None) or (card_templates is not None) or (source_cards is not None):
                raise ValueError("A base catalog cannot be combined with raw card records")

            self._card_templates = {
                template.id: template
                for template in base.cards.templates
            }
            self._card_implementations = dict(base.card_implementations)
            self._artifacts = dict(base.artifacts)
            self._enchantments = dict(base.enchantments)
            self._souls = dict(base.souls)
            self._presentations = {
                presentation.key: presentation
                for presentation in base.presentation.presentations
            }
            self._runtime_limits = base.runtime_limits
            self._source_cards = list(base.source_cards)
            return

        if (card_records is not None) and (card_templates is not None):
            raise ValueError("ContentBuilder cannot combine card records and card templates")
        if (card_records is None) and (card_templates is None):
            raise ValueError("ContentBuilder requires card records or card templates")
        if source_cards is None:
            raise ValueError("ContentBuilder requires source cards")

        if card_records is not None:
            library = CardLibrary.from_records(card_records)
        else:
            library = CardLibrary(card_templates)

        self._card_templates = {
            template.id: template
            for template in library.templates
        }

        self._card_implementations: dict[int, type[Card]] = {}
        self._artifacts: dict[int, type[Artifact]] = {}
        self._enchantments: dict[str, type[Enchantment]] = {}
        self._souls: dict[str, type[Soul]] = {}
        self._presentations: dict[tuple[ContentKind, int | str], ContentPresentation] = {}
        self._runtime_limits: RuntimeLimits | None = None
        self._source_cards = list(source_cards)

    def add_module(self, module: ModuleType) -> None:
        self.add_registrations(registrations_from_module(module))

    def add_modules(self, modules: Iterable[ModuleType]) -> None:
        for module in modules:
            self.add_module(module)

    def set_runtime_limits(self, limits: RuntimeLimits | None) -> None:
        self._runtime_limits = limits

    def add_registrations(self, registrations: Iterable[ContentRegistration]) -> None:
        for registration in registrations:
            self.add_registration(registration)

    def add_registration(self, registration: ContentRegistration) -> None:
        if registration.kind == 'card':
            self._add_card(registration)
        elif registration.kind == 'artifact':
            self._add_artifact(registration)
        elif registration.kind == 'soul':
            self._add_soul(registration)
        elif registration.kind == 'enchantment':
            self._add_enchantment(registration)
        else:
            raise ValueError(f"Unknown content registration kind {registration.kind!r}")

    def _add_presentation(self, registration: ContentRegistration) -> None:
        presentation = registration.presentation
        if presentation is None:
            return

        expected_key = (registration.kind, registration.content_id)
        if presentation.key != expected_key:
            raise ValueError(
                f"Presentation key {presentation.key!r} does not match registration {expected_key!r}"
            )

        if expected_key in self._presentations:
            raise ValueError(f"Duplicate presentation for {expected_key!r}")

        self._presentations[expected_key] = presentation

    def _add_card(self, registration: ContentRegistration) -> None:
        if type(registration.content_id) is not int:
            raise TypeError("Card registration ID must be an integer")

        card_id = registration.content_id
        implementation = registration.implementation

        if not issubclass(implementation, Card):
            raise TypeError("A card registration must use a Card implementation")

        if card_id in self._card_implementations:
            raise ValueError(f"Duplicate card implementation ID {card_id}")

        template = registration.template
        if template is not None:
            if template.id != card_id:
                raise ValueError(
                    f"Card registration ID {card_id} does not match template ID {template.id}"
                )

            if card_id in self._card_templates:
                raise ValueError(f"Duplicate card template ID {card_id}")

            normalized_name = normalize_content_name(template.name)
            if any(
                normalize_content_name(existing.name) == normalized_name
                for existing in self._card_templates.values()
            ):
                raise ValueError(f"Duplicate card name {template.name!r}")

            self._card_templates[card_id] = template

        else:
            existing = self._card_templates.get(card_id)
            if existing is None:
                raise ValueError(f"Card implementation {card_id} has no matching card template")

            declared_abilities = frozenset(
                Ability[name]
                for name in implementation.declared_ability_names()
            )
            self._card_templates[card_id] = replace(
                existing,
                abilities=declared_abilities,
            )

        self._card_implementations[card_id] = implementation
        self._add_presentation(registration)

    def _add_artifact(self, registration: ContentRegistration) -> None:
        if type(registration.content_id) is not int:
            raise TypeError("Artifact registration ID must be an integer")

        artifact_id = registration.content_id
        implementation = registration.implementation

        if not issubclass(implementation, Artifact):
            raise TypeError("An Artifact registration must use an Artifact implementation")
        if artifact_id in self._artifacts:
            raise ValueError(f"Duplicate Artifact ID {artifact_id}")

        self._artifacts[artifact_id] = implementation
        self._add_presentation(registration)

    def _add_soul(self, registration: ContentRegistration) -> None:
        if not isinstance(registration.content_id, str):
            raise TypeError("Soul registration ID must be a string")

        soul_id = registration.content_id
        implementation = registration.implementation

        if not issubclass(implementation, Soul):
            raise TypeError("A Soul registration must use a Soul implementation")
        if soul_id in self._souls:
            raise ValueError(f"Duplicate Soul ID {soul_id!r}")

        self._souls[soul_id] = implementation
        self._add_presentation(registration)

    def _add_enchantment(self, registration: ContentRegistration) -> None:
        if not isinstance(registration.content_id, str):
            raise TypeError("Enchantment registration ID must be a string")

        enchantment_id = registration.content_id
        implementation = registration.implementation

        if not issubclass(implementation, Enchantment):
            raise TypeError("An Enchantment registration must use an Enchantment implementation")
        if enchantment_id in self._enchantments:
            raise ValueError(f"Duplicate Enchantment ID {enchantment_id!r}")

        self._enchantments[enchantment_id] = implementation
        self._add_presentation(registration)

    def finalize(self) -> ContentCatalog:
        cards = CardLibrary(self._card_templates.values())
        artifacts = dict(self._artifacts)
        enchantments = dict(self._enchantments)
        artifact_names = _definitions_by_name(artifacts.values(), kind='Artifact')
        enchantment_names = _definitions_by_name(enchantments.values(), kind='Enchantment')

        presentation = ContentRegistry()
        for item in sorted(
            self._presentations.values(),
            key=lambda value: (value.kind, str(value.content_id)),
        ):
            presentation.register_presentation(item)

        presentation.finalize()

        return ContentCatalog(
            cards=cards,
            card_implementations=dict(self._card_implementations),
            artifacts=artifacts,
            enchantments=enchantments,
            souls=dict(self._souls),
            artifacts_by_name=artifact_names,
            enchantments_by_name=enchantment_names,
            presentation=presentation,
            frontend=FrontendContentCatalog.build(
                source_cards=self._source_cards,
                cards=cards,
                artifacts=artifacts,
                enchantments=enchantments,
                souls=self._souls,
                presentation=presentation,
            ),
            source_cards=list(self._source_cards),
            runtime_limits=self._runtime_limits,
        )
