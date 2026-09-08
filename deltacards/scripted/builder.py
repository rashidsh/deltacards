from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from deltacards.content.catalog import ContentBuilder, ContentCatalog
from deltacards.content.library import normalize_content_name
from deltacards.content.registration import ContentRegistration
from deltacards.content.registry import (
    ClientImage,
    ContentPresentation,
    ExistingImage,
    ImageSpec,
    LocalizedText,
)
from deltacards.model.artifacts import ArtifactRarity
from deltacards.model.enums import (
    CardKeyword,
    CardRarity,
    CardStatusId,
    CardToggleableAbility,
    Expansion,
    Tribe,
)
from deltacards.model.templates import MonsterTemplate, SpellTemplate
from deltacards.scripted.ir import NodeBudget, compile_program
from deltacards.scripted.limits import (
    DEFAULT_SCRIPTED_CONTENT_LIMITS,
    ScriptedContentLimits,
)
from deltacards.scripted.runtime import (
    CompiledProgram,
    ScriptedArtifact,
    ScriptedDefinition,
    ScriptedEnchantment,
    ScriptedMonster,
    ScriptedSpell,
    make_scripted_type,
)
from deltacards.scripted.validation import (
    ParsedEntity,
    ParsedPack,
    ScriptedDiagnostic,
    ValidationContext,
    parse_pack,
)


SCRIPTED_CARD_ID_START = 1_000_000_000
SCRIPTED_ARTIFACT_ID_START = 1_000_000_000
SCRIPTED_NUMERIC_ID_SPAN = 1_000_000_000

_SOURCE_DIRECTORY = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class ScriptedPackValidation:
    diagnostics: tuple[ScriptedDiagnostic, ...]
    assigned_ids: dict[str, int | str]

    @property
    def valid(self) -> bool:
        return not self.diagnostics

    def to_dict(self) -> dict[str, Any]:
        return {
            'valid': self.valid,
            'assignedIds': dict(self.assigned_ids),
            'diagnostics': [
                diagnostic.to_dict()
                for diagnostic in self.diagnostics
            ],
        }


@dataclass(frozen=True, slots=True)
class ScriptedCatalogBuild:
    catalog: ContentCatalog
    pack_id: str
    pack_name: str
    assigned_ids: dict[str, int | str]


class ScriptedContentValidationError(ValueError):
    def __init__(self, diagnostics: tuple[ScriptedDiagnostic, ...]):
        super().__init__("Scripted content pack is invalid")
        self.diagnostics = diagnostics


@dataclass(frozen=True, slots=True)
class _Compilation:
    pack: ParsedPack | None
    validation: ScriptedPackValidation
    programs: dict[str, CompiledProgram]


def _validate_unique_content_ids(
    pack: ParsedPack,
    validation: ValidationContext,
) -> None:
    seen: dict[str, ParsedEntity] = {}

    for entity in pack.entities:
        existing = seen.get(entity.content_id)
        if existing is not None:
            validation.error(
                'DUPLICATE_CONTENT_ID',
                f"Content UUID {entity.content_id!r} is used more than once.",
                path=f"{entity.path}.contentId",
                entity_id=entity.content_id,
            )
            continue

        seen[entity.content_id] = entity


def _validate_unique_names(
    pack: ParsedPack,
    base: ContentCatalog,
    validation: ValidationContext,
) -> None:
    base_names = {
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
    custom_names: dict[str, set[str]] = {
        'card': set(),
        'artifact': set(),
        'enchantment': set(),
    }

    for entity in pack.entities:
        group = (
            'card'
            if entity.kind in ('monster', 'spell')
            else entity.kind
        )
        name = normalize_content_name(entity.definition['name'])

        if name in base_names[group]:
            validation.error(
                'DUPLICATE_NAME',
                f"{entity.definition['name']!r} conflicts with existing {group} content.",
                path=f"{entity.path}.definition.name",
                entity_id=entity.content_id,
            )
            continue

        if name in custom_names[group]:
            validation.error(
                'DUPLICATE_NAME',
                f"{entity.definition['name']!r} is used more than once for {group} content.",
                path=f"{entity.path}.definition.name",
                entity_id=entity.content_id,
            )
            continue

        custom_names[group].add(name)


def _allocate_numeric_ids(
    entities: list[ParsedEntity],
    occupied: set[int],
    *,
    start: int,
    validation: ValidationContext,
    content_kind: str,
) -> dict[str, int]:
    result = {}

    for entity in sorted(entities, key=lambda item: item.content_id):
        candidate = start + (UUID(entity.content_id).int % SCRIPTED_NUMERIC_ID_SPAN)

        if candidate in occupied:
            validation.error(
                'NUMERIC_ID_COLLISION',
                (
                    f"{content_kind} UUID {entity.content_id!r} maps to "
                    f"occupied numeric ID {candidate}. Generate a new UUID."
                ),
                path=f"{entity.path}.contentId",
                entity_id=entity.content_id,
            )
            continue

        result[entity.content_id] = candidate
        occupied.add(candidate)

    return result


def _assign_ids(
    pack: ParsedPack,
    base: ContentCatalog,
    validation: ValidationContext,
) -> dict[str, int | str]:
    cards = [
        entity
        for entity in pack.entities
        if entity.kind in ('monster', 'spell')
    ]
    artifacts = [
        entity
        for entity in pack.entities
        if entity.kind == 'artifact'
    ]
    enchantments = [
        entity
        for entity in pack.entities
        if entity.kind == 'enchantment'
    ]

    result: dict[str, int | str] = {}
    result.update(_allocate_numeric_ids(
        cards,
        {template.id for template in base.cards.templates},
        start=SCRIPTED_CARD_ID_START,
        validation=validation,
        content_kind='Card',
    ))
    result.update(_allocate_numeric_ids(
        artifacts,
        set(base.artifacts),
        start=SCRIPTED_ARTIFACT_ID_START,
        validation=validation,
        content_kind='Artifact',
    ))

    for entity in sorted(enchantments, key=lambda item: item.content_id):
        key = f"user-{entity.content_id.replace('-', '')}"
        if key in base.enchantments:
            validation.error(
                'ENCHANTMENT_ID_COLLISION',
                f"Generated Enchantment key {key!r} is already occupied.",
                path=entity.path,
                entity_id=entity.content_id,
            )
            continue

        result[entity.content_id] = key

    return result


def _presentation(
    *,
    kind: str,
    content_id: int | str,
    definition: dict[str, Any],
    image: ImageSpec,
) -> ContentPresentation:
    return ContentPresentation(
        kind=kind,
        content_id=content_id,
        localizations={
            'en': LocalizedText(
                name=definition['name'],
                description=definition['description'],
            ),
        },
        image=image,
        source_directory=_SOURCE_DIRECTORY,
    )


def _scripted_image(raw: dict[str, Any] | None) -> ImageSpec:
    if raw is None:
        return ClientImage(None)

    if raw['source'] == 'existing':
        return ExistingImage(raw['name'])

    return ClientImage(raw['assetId'])


def _card_keywords(names: list[str]) -> CardKeyword:
    result = CardKeyword.NONE
    for name in names:
        result |= CardKeyword[name]

    return result


def _active_card_abilities(program: CompiledProgram) -> frozenset[CardToggleableAbility]:
    result = set()

    for ability in program.abilities:
        try:
            result.add(CardToggleableAbility(ability.value))
        except ValueError:
            pass

    return frozenset(result)


def _build_card_registration(
    entity: ParsedEntity,
    assigned_id: int,
    program: CompiledProgram,
) -> ContentRegistration:
    definition = entity.definition
    image = _scripted_image(definition['image'])
    scripted_definition = ScriptedDefinition(
        content_id=entity.content_id,
        kind=entity.kind,
        program=program,
    )

    if entity.kind == 'monster':
        implementation = make_scripted_type(
            ScriptedMonster,
            scripted_definition,
        )
        template = MonsterTemplate(
            id=assigned_id,
            name=definition['name'],
            image=image,
            rarity=CardRarity[definition['rarity']],
            cost=definition['cost'],
            abilities=frozenset(program.abilities),
            keywords=_card_keywords(definition['keywords']),
            statuses={
                CardStatusId[name]: counter
                for name, counter in definition['statuses'].items()
            },
            active_abilities=_active_card_abilities(program),
            expansion=Expansion.BASE,
            tribes=tuple(
                Tribe[name]
                for name in definition['tribes']
            ),
            soul_id=None,
            attack=definition['attack'],
            hp=definition['hp'],
        )

    else:
        implementation = make_scripted_type(
            ScriptedSpell,
            scripted_definition,
        )
        template = SpellTemplate(
            id=assigned_id,
            name=definition['name'],
            image=image,
            rarity=CardRarity[definition['rarity']],
            cost=definition['cost'],
            abilities=frozenset(program.abilities),
            keywords=_card_keywords(definition['keywords']),
            statuses={
                CardStatusId[name]: counter
                for name, counter in definition['statuses'].items()
            },
            active_abilities=_active_card_abilities(program),
            expansion=Expansion.BASE,
            tribes=(),
            soul_id=definition['soulId'],
        )

    return ContentRegistration(
        kind='card',
        content_id=assigned_id,
        implementation=implementation,
        template=template,
        presentation=_presentation(
            kind='card',
            content_id=assigned_id,
            definition=definition,
            image=image,
        ),
    )


def _build_artifact_registration(
    entity: ParsedEntity,
    assigned_id: int,
    program: CompiledProgram,
) -> ContentRegistration:
    definition = entity.definition
    image = _scripted_image(definition['image'])
    scripted_definition = ScriptedDefinition(
        content_id=entity.content_id,
        kind=entity.kind,
        program=program,
    )
    implementation = make_scripted_type(
        ScriptedArtifact,
        scripted_definition,
        attributes={
            'definition_id': assigned_id,
            'name': definition['name'],
            'rarity': ArtifactRarity[definition['rarity']],
            'initial_counter': definition['initialCounter'],
        },
    )

    return ContentRegistration(
        kind='artifact',
        content_id=assigned_id,
        implementation=implementation,
        presentation=_presentation(
            kind='artifact',
            content_id=assigned_id,
            definition=definition,
            image=image,
        ),
    )


def _build_enchantment_registration(
    entity: ParsedEntity,
    assigned_id: str,
    program: CompiledProgram,
) -> ContentRegistration:
    definition = entity.definition
    image = _scripted_image(definition['image'])
    scripted_definition = ScriptedDefinition(
        content_id=entity.content_id,
        kind=entity.kind,
        program=program,
    )
    implementation = make_scripted_type(
        ScriptedEnchantment,
        scripted_definition,
        attributes={
            'definition_id': assigned_id,
            'name': definition['name'],
            'initial_counter': definition['initialCounter'],
        },
    )

    return ContentRegistration(
        kind='enchantment',
        content_id=assigned_id,
        implementation=implementation,
        presentation=_presentation(
            kind='enchantment',
            content_id=assigned_id,
            definition=definition,
            image=image,
        ),
    )


def _build_registrations(
    pack: ParsedPack,
    assigned_ids: dict[str, int | str],
    programs: dict[str, CompiledProgram],
) -> tuple[ContentRegistration, ...]:
    result = []

    for entity in sorted(pack.entities, key=lambda item: item.content_id):
        assigned_id = assigned_ids[entity.content_id]
        program = programs[entity.content_id]

        if entity.kind in ('monster', 'spell'):
            result.append(
                _build_card_registration(
                    entity,
                    int(assigned_id),
                    program,
                )
            )
        elif entity.kind == 'artifact':
            result.append(
                _build_artifact_registration(
                    entity,
                    int(assigned_id),
                    program,
                )
            )
        else:
            result.append(
                _build_enchantment_registration(
                    entity,
                    str(assigned_id),
                    program,
                )
            )

    return tuple(result)


def _invalid_compilation(
    validation: ValidationContext,
    assigned_ids: dict[str, int | str] | None = None,
    pack: ParsedPack | None = None,
) -> _Compilation:
    return _Compilation(
        pack=pack,
        validation=ScriptedPackValidation(
            diagnostics=tuple(validation.diagnostics),
            assigned_ids=dict(assigned_ids or {}),
        ),
        programs={},
    )


def _compile_pack(
    pack_data: dict[str, Any],
    *,
    base: ContentCatalog,
    limits: ScriptedContentLimits,
) -> _Compilation:
    if type(pack_data) is not dict:
        raise TypeError("Scripted content pack must be a dictionary")

    validation = ValidationContext(limits)
    pack = parse_pack(
        pack_data,
        base=base,
        validation=validation,
    )
    if pack is None:
        return _invalid_compilation(validation)

    _validate_unique_content_ids(pack, validation)
    _validate_unique_names(pack, base, validation)
    if validation.diagnostics:
        return _invalid_compilation(validation, pack=pack)

    assigned_ids = _assign_ids(pack, base, validation)
    if validation.diagnostics:
        return _invalid_compilation(
            validation,
            assigned_ids,
            pack,
        )

    budget = NodeBudget()
    programs = {}

    for entity in pack.entities:
        program = compile_program(
            entity,
            base=base,
            entities=pack.entities,
            validation=validation,
            budget=budget,
        )
        if program is not None:
            programs[entity.content_id] = program

    if validation.diagnostics:
        return _invalid_compilation(
            validation,
            assigned_ids,
            pack,
        )

    return _Compilation(
        pack=pack,
        validation=ScriptedPackValidation(
            diagnostics=(),
            assigned_ids=dict(assigned_ids),
        ),
        programs=programs,
    )


def validate_scripted_pack(
    pack: dict[str, Any],
    *,
    base: ContentCatalog,
    limits: ScriptedContentLimits = DEFAULT_SCRIPTED_CONTENT_LIMITS,
) -> ScriptedPackValidation:
    return _compile_pack(
        pack,
        base=base,
        limits=limits,
    ).validation


def build_scripted_catalog(
    pack: dict[str, Any],
    *,
    base: ContentCatalog,
    limits: ScriptedContentLimits = DEFAULT_SCRIPTED_CONTENT_LIMITS,
) -> ScriptedCatalogBuild:
    compilation = _compile_pack(
        pack,
        base=base,
        limits=limits,
    )
    if not compilation.validation.valid:
        raise ScriptedContentValidationError(
            compilation.validation.diagnostics
        )

    assert compilation.pack is not None

    registrations = _build_registrations(
        compilation.pack,
        compilation.validation.assigned_ids,
        compilation.programs,
    )

    builder = ContentBuilder(base=base)
    runtime_limits = limits.runtime_limits
    if base.runtime_limits is not None:
        runtime_limits = base.runtime_limits.restricted_by(runtime_limits)

    builder.set_runtime_limits(runtime_limits)
    builder.add_registrations(registrations)
    catalog = builder.finalize()

    return ScriptedCatalogBuild(
        catalog=catalog,
        pack_id=compilation.pack.pack_id,
        pack_name=compilation.pack.name,
        assigned_ids=dict(compilation.validation.assigned_ids),
    )
