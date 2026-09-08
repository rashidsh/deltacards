import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from deltacards.content.catalog import ContentCatalog
from deltacards.model.artifacts import ArtifactRarity
from deltacards.model.enums import (
    CardKeyword,
    CardRarity,
    CardStatusId,
    Tribe,
)
from deltacards.scripted.limits import ScriptedContentLimits


IMAGE_NAME_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')


@dataclass(frozen=True, slots=True)
class ScriptedDiagnostic:
    code: str
    message: str
    path: str
    entity_id: str | None = None
    node_id: str | None = None
    severity: str = 'error'

    def to_dict(self) -> dict[str, Any]:
        return {
            'entityId': self.entity_id,
            'nodeId': self.node_id,
            'severity': self.severity,
            'code': self.code,
            'path': self.path,
            'message': self.message,
        }


@dataclass(frozen=True, slots=True)
class ParsedEntity:
    content_id: str
    kind: str
    definition: dict[str, Any]
    implementation: dict[str, Any]
    path: str


@dataclass(frozen=True, slots=True)
class ParsedPack:
    pack_id: str
    name: str
    entities: list[ParsedEntity]


class ValidationContext:
    def __init__(self, limits: ScriptedContentLimits):
        self.limits = limits
        self.diagnostics: list[ScriptedDiagnostic] = []

    def error(
        self,
        code: str,
        message: str,
        *,
        path: str,
        entity_id: str | None = None,
        node_id: str | None = None,
    ) -> None:
        self.diagnostics.append(
            ScriptedDiagnostic(
                code=code,
                message=message,
                path=path,
                entity_id=entity_id,
                node_id=node_id,
            )
        )


def _required(raw: dict[str, Any], name: str) -> Any:
    try:
        return raw[name]
    except KeyError as exc:
        raise ValueError(f"Missing required field {name!r}.") from exc


def _object(raw: Any, name: str) -> dict[str, Any]:
    if type(raw) is not dict:
        raise ValueError(f"{name} must be an object.")

    return raw


def _string(
    raw: Any,
    *,
    name: str,
    minimum_length: int = 0,
    maximum_length: int = 128,
    reject_html: bool = False,
) -> str:
    if type(raw) is not str:
        raise ValueError(f"{name} must be a string.")

    value = raw.strip()
    if not minimum_length <= len(value) <= maximum_length:
        raise ValueError(
            f"{name} must contain between {minimum_length} and "
            f"{maximum_length} characters."
        )

    if reject_html and ('<' in value or '>' in value):
        raise ValueError(f"{name} cannot contain '<' or '>'.")

    return value


def _integer(
    raw: Any,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(raw) is not int:
        raise ValueError(f"{name} must be an integer.")

    if not minimum <= raw <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")

    return raw


def _uuid(raw: Any, *, name: str) -> str:
    if type(raw) is not str:
        raise ValueError(f"{name} must be a canonical UUID string.")

    try:
        value = str(UUID(raw))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{name} must be a canonical UUID string.") from exc

    if value != raw:
        raise ValueError(f"{name} must use canonical UUID form {value!r}.")

    return value


def _enum_name(raw: Any, enum_type: type[Enum], *, name: str) -> str:
    if (type(raw) is not str) or (raw not in enum_type.__members__):
        raise ValueError(f"{name} has unknown {enum_type.__name__} value {raw!r}.")

    return raw


def _enum_list(raw: Any, enum_type: type[Enum], *, name: str) -> list[str]:
    if type(raw) is not list:
        raise ValueError(f"{name} must be an array.")

    result = []
    for index, item in enumerate(raw):
        value = _enum_name(
            item,
            enum_type,
            name=f"{name}[{index}]",
        )
        if value not in result:
            result.append(value)

    return result


def _statuses(
    raw: Any,
    *,
    name: str,
    limits: ScriptedContentLimits,
) -> dict[str, int]:
    raw = _object(raw, name)

    result = {}
    for status_name, counter in raw.items():
        parsed_name = _enum_name(
            status_name,
            CardStatusId,
            name=f"{name}.{status_name}",
        )
        result[parsed_name] = _integer(
            counter,
            name=f"{name}.{status_name}",
            minimum=1,
            maximum=limits.max_counter,
        )

    return result


def _image(raw: Any) -> dict[str, str] | None:
    if raw is None:
        return None

    raw = _object(raw, 'image')
    source = _required(raw, 'source')

    if source == 'existing':
        if set(raw) != {'source', 'name'}:
            raise ValueError(
                "An existing image requires exactly source and name."
            )

        name = _string(
            raw['name'],
            name='image.name',
            minimum_length=1,
            maximum_length=128,
        )
        if IMAGE_NAME_PATTERN.fullmatch(name) is None:
            raise ValueError(
                "image.name may contain only letters, numbers, '_' and '-'."
            )

        return {
            'source': source,
            'name': name,
        }

    if source == 'client':
        if set(raw) != {'source', 'assetId'}:
            raise ValueError(
                "A client image requires exactly source and assetId."
            )

        return {
            'source': source,
            'assetId': _uuid(raw['assetId'], name='image.assetId'),
        }

    raise ValueError("image.source must be existing or client.")


def _common_definition(
    raw: dict[str, Any],
    *,
    limits: ScriptedContentLimits,
) -> dict[str, Any]:
    return {
        'name': _string(
            _required(raw, 'name'),
            name='name',
            minimum_length=1,
            maximum_length=limits.max_name_length,
            reject_html=True,
        ),
        'description': _string(
            _required(raw, 'description'),
            name='description',
            minimum_length=0,
            maximum_length=limits.max_description_length,
            reject_html=True,
        ),
        'image': _image(
            _required(raw, 'image'),
        ),
    }


def _card_rarity(raw: Any) -> str:
    return _enum_name(raw, CardRarity, name='rarity')


def _artifact_rarity(raw: Any) -> str:
    return _enum_name(raw, ArtifactRarity, name='rarity')


def _parse_definition(
    raw: Any,
    kind: str,
    *,
    limits: ScriptedContentLimits,
    base: ContentCatalog,
) -> dict[str, Any]:
    raw = _object(raw, 'definition')
    result = _common_definition(raw, limits=limits)

    if kind in ('monster', 'spell'):
        result.update({
            'rarity': _card_rarity(_required(raw, 'rarity')),
            'cost': _integer(
                _required(raw, 'cost'),
                name='cost',
                minimum=0,
                maximum=limits.max_card_stat,
            ),
        })

        result.update({
            'keywords': _enum_list(
                _required(raw, 'keywords'),
                CardKeyword,
                name='keywords',
            ),
            'statuses': _statuses(
                _required(raw, 'statuses'),
                name='statuses',
                limits=limits,
            ),
        })

    if kind == 'monster':
        result.update({
            'attack': _integer(
                _required(raw, 'attack'),
                name='attack',
                minimum=0,
                maximum=limits.max_card_stat,
            ),
            'hp': _integer(
                _required(raw, 'hp'),
                name='hp',
                minimum=1,
                maximum=limits.max_card_stat,
            ),
            'tribes': _enum_list(
                _required(raw, 'tribes'),
                Tribe,
                name='tribes',
            ),
        })
        return result

    if kind == 'spell':
        soul_id = _required(raw, 'soulId')
        if soul_id is not None:
            soul_id = _string(
                soul_id,
                name='soulId',
            )
            if soul_id not in base.souls:
                raise ValueError("Spell uses an unknown Soul.")

        result['soulId'] = soul_id
        return result

    result['initialCounter'] = _integer(
        _required(raw, 'initialCounter'),
        name='initialCounter',
        minimum=0,
        maximum=limits.max_counter,
    )

    if kind == 'artifact':
        result['rarity'] = _artifact_rarity(
            _required(raw, 'rarity')
        )

    return result


def _parse_entity(
    raw: Any,
    *,
    path: str,
    limits: ScriptedContentLimits,
    base: ContentCatalog,
) -> ParsedEntity:
    raw = _object(raw, 'entity')

    content_id = _uuid(
        _required(raw, 'contentId'),
        name='contentId',
    )

    kind = _required(raw, 'kind')
    if kind not in ('monster', 'spell', 'artifact', 'enchantment'):
        raise ValueError(f"Unsupported scripted content kind {kind!r}.")

    implementation = _object(
        _required(raw, 'implementation'),
        'implementation',
    )

    return ParsedEntity(
        content_id=content_id,
        kind=kind,
        definition=_parse_definition(
            _required(raw, 'definition'),
            kind,
            limits=limits,
            base=base,
        ),
        implementation=implementation,
        path=path,
    )


def _validate_pack_size(
    pack: dict[str, Any],
    validation: ValidationContext,
) -> bool:
    try:
        encoded = json.dumps(
            pack,
            ensure_ascii=False,
            allow_nan=False,
            separators=(',', ':'),
        ).encode('utf-8')
    except (RecursionError, TypeError, ValueError) as exc:
        validation.error(
            'INVALID_JSON_VALUE',
            f"Content pack contains a non-JSON-compatible value: {exc}",
            path='$',
        )
        return False

    if len(encoded) > validation.limits.max_pack_bytes:
        validation.error(
            'PACK_TOO_LARGE',
            "Serialized content pack exceeds the size limit.",
            path='$',
        )
        return False

    return True


def parse_pack(
    pack: dict[str, Any],
    *,
    base: ContentCatalog,
    validation: ValidationContext,
) -> ParsedPack | None:
    if not _validate_pack_size(pack, validation):
        return None

    try:
        pack = _object(pack, 'pack')

        schema_version = _required(pack, 'schemaVersion')
        if schema_version != 1:
            validation.error(
                'UNSUPPORTED_SCHEMA_VERSION',
                "Only scripted content schema version 1 is supported.",
                path='$.schemaVersion',
            )

        pack_id = _uuid(
            _required(pack, 'packId'),
            name='packId',
        )
        name = _string(
            _required(pack, 'name'),
            name='name',
            minimum_length=1,
            maximum_length=validation.limits.max_name_length,
            reject_html=True,
        )

        raw_entities = _required(pack, 'entities')
        if type(raw_entities) is not list:
            raise ValueError("entities must be an array.")

    except ValueError as exc:
        validation.error(
            'INVALID_PACK',
            str(exc),
            path='$',
        )
        return None

    if len(raw_entities) > validation.limits.max_entities:
        validation.error(
            'TOO_MANY_ENTITIES',
            f"A pack may contain at most {validation.limits.max_entities} entities.",
            path='$.entities',
        )
        raw_entities = raw_entities[:validation.limits.max_entities]

    entities = []
    for index, raw_entity in enumerate(raw_entities):
        path = f"$.entities[{index}]"
        entity_id = (
            raw_entity.get('contentId')
            if type(raw_entity) is dict and type(raw_entity.get('contentId')) is str
            else None
        )

        try:
            entities.append(
                _parse_entity(
                    raw_entity,
                    path=path,
                    limits=validation.limits,
                    base=base,
                )
            )
        except (TypeError, ValueError) as exc:
            validation.error(
                'INVALID_ENTITY',
                str(exc),
                path=path,
                entity_id=entity_id,
            )

    return ParsedPack(
        pack_id=pack_id,
        name=name,
        entities=entities,
    )
