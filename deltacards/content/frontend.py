import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from deltacards.content.library import CardLibrary
from deltacards.content.registry import (
    ContentRegistry,
    enchantment_asset_name,
    soul_frontend_name,
)
from deltacards.model.artifacts import (
    Artifact,
    ArtifactRarity,
    QuestArtifact,
)
from deltacards.model.enchantments import Enchantment
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
from deltacards.model.souls import Soul


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


def custom_card_view(
    template: CardTemplate,
    presentation: ContentRegistry,
) -> dict[str, Any]:
    default_image = (
        template.image
        if isinstance(template.image, str)
        else template.name
    )
    image = presentation.image(
        'card',
        template.id,
        default_name=default_image,
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

    if image.client_managed:
        result['clientAssetId'] = image.client_asset_id

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


def custom_artifact_view(
    artifact_id: int,
    artifact_type: type[Artifact],
    presentation: ContentRegistry,
) -> dict[str, Any]:
    artifact_images = presentation.artifact_images(
        artifact_id,
        default_name=artifact_type.name,
    )
    image = artifact_images.image
    is_quest = issubclass(artifact_type, QuestArtifact)

    result = {
        'id': artifact_id,
        'name': artifact_type.name,
        'image': image.name,
        'rarity': artifact_type.rarity.name,
        'legendary': artifact_type.rarity is ArtifactRarity.LEGENDARY,
        'artifactType': 1 if is_quest else 0,
        'custom': 0,
        'disabled': False,
    }

    if image.url is not None:
        result['imageUrl'] = image.url

    if image.client_managed:
        result['clientAssetId'] = image.client_asset_id

    if is_quest:
        goal = artifact_type.quest_goal
        if goal is None:
            raise ValueError(f"Quest Artifact {artifact_id} has no goal")

        result['progress'] = 0
        result['goal'] = goal
        result['overlayUrl'] = artifact_images.overlay_url

    return result


def custom_enchantment_view(
    enchantment_id: str,
    enchantment_type: type[Enchantment],
    presentation: ContentRegistry,
) -> dict[str, Any]:
    frontend_name = enchantment_asset_name(enchantment_id)
    images = presentation.enchantment_images(
        enchantment_id,
        default_name=enchantment_type.name,
    )

    result = {
        'id': enchantment_id,
        'name': frontend_name,
        'backgroundUrl': images.background_url,
        'overlayUrl': images.overlay_url,
        'logUrl': images.log_url,
    }

    if images.background_client_managed:
        result['clientAssetId'] = images.background_client_asset_id

    return result


def custom_soul_view(
    soul_id: str,
    soul_type: type[Soul],
    presentation: ContentRegistry,
) -> dict[str, Any]:
    frontend_name = soul_frontend_name(soul_id)
    image = presentation.image(
        'soul',
        soul_id,
        default_name=soul_type.name,
    )

    result = {
        'id': soul_id,
        'name': frontend_name,
    }

    if image.url is not None:
        result['imageUrl'] = image.url

    if image.client_managed:
        result['clientAssetId'] = image.client_asset_id

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
    cards_version: int
    cards: list

    _custom_content: dict
    _custom_cards_by_id: dict[int, dict]
    _custom_artifacts_by_id: dict[int, dict]

    @classmethod
    def build(
        cls,
        *,
        source_cards: list[dict],
        cards: CardLibrary,
        artifacts: Mapping[int, type[Artifact]],
        enchantments: Mapping[str, type[Enchantment]],
        souls: Mapping[str, type[Soul]],
        presentation: ContentRegistry,
    ) -> 'FrontendContentCatalog':
        custom_cards = [
            custom_card_view(
                cards.get(card_id),
                presentation,
            )
            for card_id in presentation.custom_ids('card')
        ]

        custom_artifacts = [
            custom_artifact_view(
                artifact_id,
                artifacts[artifact_id],
                presentation,
            )
            for artifact_id in presentation.custom_ids('artifact')
        ]
        custom_enchantments = [
            custom_enchantment_view(
                enchantment_id,
                enchantments[enchantment_id],
                presentation,
            )
            for enchantment_id in presentation.custom_ids('enchantment')
        ]
        custom_souls = [
            custom_soul_view(
                soul_id,
                souls[soul_id],
                presentation,
            )
            for soul_id in presentation.custom_ids('soul')
        ]

        frontend_cards = sorted(
            [
                *source_cards,
                *custom_cards,
            ],
            key=lambda card: int(card['fixedId']),
        )

        custom_content = {
            'cards': custom_cards,
            'artifacts': custom_artifacts,
            'enchantments': custom_enchantments,
            'souls': custom_souls,
            'contentIds': {
                'card': list(presentation.custom_ids('card')),
                'artifact': list(presentation.custom_ids('artifact')),
                'enchantment': list(presentation.custom_ids('enchantment')),
                'soul': list(presentation.custom_ids('soul')),
            },
        }

        return cls(
            cards_version=_cards_version(frontend_cards),
            cards=frontend_cards,
            _custom_content=custom_content,
            _custom_cards_by_id={
                int(card['id']): card
                for card in custom_cards
            },
            _custom_artifacts_by_id={
                int(artifact['id']): artifact
                for artifact in custom_artifacts
            },
        )

    @property
    def custom_cards(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.custom_content_view()['cards'])

    @property
    def custom_artifacts(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.custom_content_view()['artifacts'])

    @property
    def custom_enchantments(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.custom_content_view()['enchantments'])

    @property
    def custom_souls(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.custom_content_view()['souls'])

    def is_custom_card(self, card_id: int) -> bool:
        return card_id in self._custom_cards_by_id

    def is_custom_artifact(self, artifact_id: int) -> bool:
        return artifact_id in self._custom_artifacts_by_id

    def custom_card(self, card_id: int) -> dict[str, Any] | None:
        return self._custom_cards_by_id.get(card_id)

    def custom_artifact(self, artifact_id: int) -> dict[str, Any] | None:
        return self._custom_artifacts_by_id.get(artifact_id)

    def custom_content_view(self) -> dict[str, Any]:
        return self._custom_content
