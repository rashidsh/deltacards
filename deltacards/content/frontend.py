import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from deltacards.content.card_data import decode_source_cards
from deltacards.content.registry import CONTENT
from deltacards.model.artifacts import (
    ARTIFACTS,
    ArtifactRarity,
    QuestArtifact,
)
from deltacards.model.enchantments import ENCHANTMENTS
from deltacards.model.enums import (
    CardKeyword,
)
from deltacards.model.negative_effects import (
    NEGATIVE_KEYWORDS,
    NEGATIVE_STATUS_IDS,
)
from deltacards.model.templates import (
    CardTemplate,
    MonsterTemplate,
)


def _status_name(name: str) -> str:
    if name == 'KR':
        return name

    return ''.join(
        word.capitalize()
        for word in name.split('_')
    )


def _template_statuses(template: CardTemplate) -> list[dict[str, Any]]:
    result = []

    for keyword in CardKeyword:
        if keyword is CardKeyword.NONE:
            continue

        if keyword not in template.keywords:
            continue

        result.append({
            'statusType': 'NEGATIVE' if keyword & NEGATIVE_KEYWORDS else 'POSITIVE',
            'name': _status_name(keyword.name),
            'statusBehavior': 'UNIQUE',
            'counter': 1,
            'displayCounter': False,
        })

    for status_id, counter in template.statuses.items():
        result.append({
            'statusType': 'NEGATIVE' if status_id in NEGATIVE_STATUS_IDS else 'POSITIVE',
            'name': _status_name(status_id.value),
            'statusBehavior': 'STACKABLE',
            'counter': counter,
            'displayCounter': True,
        })

    for ability in sorted(
        template.active_abilities,
        key=lambda value: value.value,
    ):
        result.append({
            'statusType': 'POSITIVE',
            'name': _status_name(ability.value),
            'statusBehavior': 'UNIQUE',
            'counter': 1,
            'displayCounter': False,
        })

    return result


def custom_card_view(template: CardTemplate) -> dict[str, Any]:
    image = CONTENT.image(
        'card',
        template.id,
        default_name=template.image,
    )

    result = {
        'id': template.id,
        'fixedId': template.id,
        'typeCard': template.type.value,
        'name': template.name,

        'image': image.name,
        'baseImage': image.name,

        'cost': template.cost,
        'originalCost': template.cost,

        'rarity': template.rarity.name,
        'extension': template.expansion.name,

        'shiny': False,
        'typeSkin': 0,

        'tribes': [
            tribe.name
            for tribe in template.tribes
        ],
        'statuses': _template_statuses(template),
    }

    if image.url is not None:
        result['imageUrl'] = image.url
        result['baseImageUrl'] = image.url

    if template.soul_id is not None:
        result['soul'] = {
            'name': template.soul_id.upper(),
        }

    if isinstance(template, MonsterTemplate):
        result.update({
            'attack': template.attack,
            'originalAttack': template.attack,
            'hp': template.hp,
            'maxHp': template.hp,
            'originalHp': template.hp,
        })

    return result


def custom_artifact_view(artifact_id: int) -> dict[str, Any]:
    artifact_type = ARTIFACTS[artifact_id]
    artifact_images = CONTENT.artifact_images(
        artifact_id,
        default_name=artifact_type.name,
    )
    image = artifact_images.image
    is_quest = issubclass(artifact_type, QuestArtifact)

    result = {
        'id': artifact_id,
        'name': artifact_type.name,
        'image': image.name,
        'legendary': artifact_type.rarity is ArtifactRarity.LEGENDARY,
        'artifactType': 1 if is_quest else 0,
        'custom': 0,
        'disabled': False,
    }

    if image.url is not None:
        result['imageUrl'] = image.url

    if is_quest:
        goal = artifact_type.quest_goal
        if goal is None:
            raise ValueError(f"Quest Artifact {artifact_id} has no goal")

        result['progress'] = 0
        result['goal'] = goal
        result['overlayUrl'] = artifact_images.overlay_url

    return result


def custom_enchantment_view(enchantment_id: str) -> dict[str, Any]:
    enchantment_type = ENCHANTMENTS[enchantment_id]
    frontend_name = CONTENT.frontend_name(
        'enchantment',
        enchantment_id,
        default_name=enchantment_type.name,
    )
    images = CONTENT.enchantment_images(
        enchantment_id,
        default_name=enchantment_type.name,
    )

    result = {
        'id': enchantment_id,
        'name': frontend_name,
        'assetName': images.asset_name,
        'backgroundUrl': images.background_url,
        'overlayUrl': images.overlay_url,
        'logUrl': images.log_url,
    }

    return result


def custom_soul_view(soul_id: str) -> dict[str, Any]:
    frontend_name = CONTENT.frontend_name(
        'soul',
        soul_id,
        default_name=soul_id.upper(),
    )
    image = CONTENT.image(
        'soul',
        soul_id,
        default_name=frontend_name,
    )

    result = {
        'id': soul_id,
        'name': frontend_name,
        'assetName': image.name,
    }

    if image.url is not None:
        result['imageUrl'] = image.url

    return result


def _cards_version(cards: list[dict[str, Any]]) -> int:
    encoded = json.dumps(
        cards,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')

    digest = sha256(encoded).digest()

    # A 48-bit value remains exactly representable by JavaScript Number.
    return int.from_bytes(digest[:6], 'big') or 1


@dataclass(frozen=True, slots=True)
class FrontendContentCatalog:
    cards: tuple[dict[str, Any], ...]

    custom_cards: tuple[dict[str, Any], ...]
    custom_artifacts: tuple[dict[str, Any], ...]
    custom_enchantments: tuple[dict[str, Any], ...]
    custom_souls: tuple[dict[str, Any], ...]

    cards_version: int

    _custom_cards_by_id: dict[int, dict[str, Any]] = field(repr=False)
    _custom_artifacts_by_id: dict[int, dict[str, Any]] = field(repr=False)

    @classmethod
    def build(cls, source_cards_path: Path) -> 'FrontendContentCatalog':
        source_cards = decode_source_cards(
            source_cards_path.read_bytes()
        )

        custom_cards = [
            custom_card_view(template)
            for template in sorted(
                CONTENT.card_templates,
                key=lambda item: item.id,
            )
        ]

        custom_artifacts = [
            custom_artifact_view(artifact_id)
            for artifact_id in CONTENT.custom_ids('artifact')
        ]
        custom_enchantments = [
            custom_enchantment_view(enchantment_id)
            for enchantment_id in CONTENT.custom_ids('enchantment')
        ]
        custom_souls = [
            custom_soul_view(soul_id)
            for soul_id in CONTENT.custom_ids('soul')
        ]

        cards = [
            *source_cards,
            *custom_cards,
        ]
        cards.sort(key=lambda card: int(card['fixedId']))

        return cls(
            cards=tuple(cards),
            custom_cards=tuple(custom_cards),
            custom_artifacts=tuple(custom_artifacts),
            custom_enchantments=tuple(custom_enchantments),
            custom_souls=tuple(custom_souls),
            cards_version=_cards_version(cards),
            _custom_cards_by_id={
                int(card['id']): card
                for card in custom_cards
            },
            _custom_artifacts_by_id={
                int(artifact['id']): artifact
                for artifact in custom_artifacts
            },
        )

    def is_custom_card(self, card_id: int) -> bool:
        return card_id in self._custom_cards_by_id

    def is_custom_artifact(self, artifact_id: int) -> bool:
        return artifact_id in self._custom_artifacts_by_id

    def custom_card(self, card_id: int) -> dict[str, Any] | None:
        return self._custom_cards_by_id.get(card_id)

    def custom_artifact(self, artifact_id: int) -> dict[str, Any] | None:
        return self._custom_artifacts_by_id.get(artifact_id)

    def custom_content_view(self) -> dict[str, Any]:
        return {
            'cards': list(self.custom_cards),
            'artifacts': list(self.custom_artifacts),
            'enchantments': list(self.custom_enchantments),
            'souls': list(self.custom_souls),
            'contentIds': {
                'card': list(CONTENT.custom_ids('card')),
                'artifact': list(CONTENT.custom_ids('artifact')),
                'enchantment': list(CONTENT.custom_ids('enchantment')),
                'soul': list(CONTENT.custom_ids('soul')),
            },
        }
