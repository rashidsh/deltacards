import mimetypes
import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, TypeAlias

from deltacards.model.templates import CardTemplate


ContentKind: TypeAlias = Literal[
    'card',
    'artifact',
    'soul',
    'enchantment',
]

ContentId: TypeAlias = int | str
ContentKey: TypeAlias = tuple[ContentKind, ContentId]

ImageRole: TypeAlias = Literal[
    'image',
    'overlay',
    'log',
]
ContentAssetKey: TypeAlias = tuple[ContentKind, ContentId, ImageRole]

@dataclass(frozen=True, slots=True)
class LocalizedText:
    name: str
    description: str = ''


@dataclass(frozen=True, slots=True)
class ExistingImage:
    name: str


@dataclass(frozen=True, slots=True)
class CustomImage:
    path: str


ImageSpec: TypeAlias = ExistingImage | CustomImage | None

DEFAULT_ENCHANTMENT_OVERLAY_IMAGE = ExistingImage(name='Incinerator')


@dataclass(frozen=True, slots=True)
class ContentPresentation:
    kind: ContentKind
    content_id: ContentId

    localizations: Mapping[str, LocalizedText]
    image: ImageSpec

    source_directory: Path
    overlay: ImageSpec = None
    log: ImageSpec = None

    @property
    def key(self) -> ContentKey:
        return self.kind, self.content_id

    def text(self, locale: str) -> LocalizedText:
        return self.localizations.get(locale, self.localizations['en'])


@dataclass(frozen=True, slots=True)
class PublishedAsset:
    url: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class FrontendImage:
    name: str
    url: str | None


@dataclass(frozen=True, slots=True)
class FrontendArtifactImages:
    image: FrontendImage
    overlay_url: str


@dataclass(frozen=True, slots=True)
class FrontendEnchantmentImages:
    asset_name: str
    background_url: str
    overlay_url: str
    log_url: str


def _ordinary_asset_name(name: str) -> str:
    value = name.strip().replace(' ', '_').replace('-', '_')
    return re.sub(r'[^A-Za-z0-9_-]', '', value)


def _enchantment_asset_name(name: str) -> str:
    if not re.search(r'[\s_-]', name):
        return re.sub(r'[^A-Za-z0-9]', '', name)

    words = re.split(r'[\s_-]+', name.strip())
    return ''.join(
        word[:1].upper() + word[1:]
        for word in words
        if word
    )


def _custom_asset_name(
    kind: ContentKind,
    content_id: ContentId,
    role: ImageRole,
) -> str:
    value = re.sub(r'[^A-Za-z0-9]+', '_', str(content_id)).strip('_')
    suffix = '' if role == 'image' else f'_{role}'
    return f'deltacards_{kind}_{value}{suffix}'


def _frontend_image_url(
    image: FrontendImage,
    directory: str,
) -> str:
    if image.url is not None:
        return image.url

    return f'/images/{directory}/{image.name}.png'


def _kebab_case(value: str) -> str:
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', value)
    return re.sub(r'[^A-Za-z0-9]+', '-', value).strip('-').lower()


def _safe_key(value: ContentId) -> str:
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def is_custom_content(kind: ContentKind, content_id: ContentId) -> bool:
    return CONTENT.is_custom(kind, content_id)


def frontend_asset_name(kind: ContentKind, name: str) -> str:
    if kind == 'card':
        return name

    if kind == 'enchantment':
        return _enchantment_asset_name(name)

    return _ordinary_asset_name(name)


class ContentRegistry:
    def __init__(self):
        self._card_templates: dict[int, CardTemplate] = {}
        self._presentations: dict[ContentKey, ContentPresentation] = {}

        self._assets_by_content: dict[ContentAssetKey, PublishedAsset] = {}
        self._assets_by_url: dict[str, PublishedAsset] = {}

    @property
    def card_templates(self) -> tuple[CardTemplate, ...]:
        return tuple(self._card_templates.values())

    @property
    def presentations(self) -> tuple[ContentPresentation, ...]:
        return tuple(self._presentations.values())

    @property
    def published_assets(self) -> tuple[PublishedAsset, ...]:
        return tuple(self._assets_by_url.values())

    def register_card(
        self,
        template: CardTemplate,
        presentation: ContentPresentation,
    ) -> None:
        if template.id in self._card_templates:
            raise ValueError(
                f"Python card template {template.id} is already registered"
            )

        self._card_templates[template.id] = template
        self.register_presentation(presentation)

    def register_presentation(
        self,
        presentation: ContentPresentation,
    ) -> None:
        if presentation.key in self._presentations:
            raise ValueError(
                f"Presentation for {presentation.key!r} is already registered"
            )

        self._presentations[presentation.key] = presentation

    def is_custom(
        self,
        kind: ContentKind,
        content_id: ContentId,
    ) -> bool:
        return (kind, content_id) in self._presentations

    def custom_ids(
        self,
        kind: ContentKind,
    ) -> tuple[ContentId, ...]:
        return tuple(sorted(
            content_id
            for entry_kind, content_id in self._presentations
            if entry_kind == kind
        ))

    def presentation(
        self,
        kind: ContentKind,
        content_id: ContentId,
    ) -> ContentPresentation | None:
        return self._presentations.get((kind, content_id))

    def finalize(self) -> None:
        """
        Resolve and freeze custom image files.

        This is run after all custom modules have been imported and before games are created.
        """
        assets_by_content = {}
        assets_by_url = {}

        for presentation in self._presentations.values():
            for role, image in (
                ('image', presentation.image),
                ('overlay', presentation.overlay),
                ('log', presentation.log),
            ):
                if not isinstance(image, CustomImage):
                    continue

                path = Path(image.path)
                if not path.is_absolute():
                    path = presentation.source_directory / path

                path = path.resolve()
                if not path.is_file():
                    raise ValueError(
                        f"Custom {role} image for {presentation.key!r} "
                        f"does not exist: {path}"
                    )

                data = path.read_bytes()
                digest = sha256(data).hexdigest()
                suffix = path.suffix.lower() or '.bin'
                url = f'/content-assets/{digest}{suffix}'

                content_type = (
                    mimetypes.guess_type(path.name)[0]
                    or 'application/octet-stream'
                )

                asset = PublishedAsset(
                    url=url,
                    content_type=content_type,
                    data=data,
                )

                asset_key = (
                    presentation.kind,
                    presentation.content_id,
                    role,
                )

                assets_by_content[asset_key] = asset
                assets_by_url[url] = asset

        self._assets_by_content = assets_by_content
        self._assets_by_url = assets_by_url

    def asset_at_url(
        self,
        url: str,
    ) -> PublishedAsset | None:
        return self._assets_by_url.get(url)

    def _frontend_image(
        self,
        kind: ContentKind,
        content_id: ContentId,
        *,
        image: ImageSpec,
        default_name: str,
        role: ImageRole,
    ) -> FrontendImage:
        if image is None:
            return FrontendImage(
                name=frontend_asset_name(kind, default_name),
                url=None,
            )

        if isinstance(image, ExistingImage):
            return FrontendImage(
                name=frontend_asset_name(kind, image.name),
                url=None,
            )

        if isinstance(image, CustomImage):
            asset = self._assets_by_content.get(
                (kind, content_id, role)
            )
            if asset is None:
                raise RuntimeError(
                    f"Content registry has not finalized {role} image for {(kind, content_id)!r}"
                )

            return FrontendImage(
                name=_custom_asset_name(kind, content_id, role),
                url=asset.url,
            )

        raise TypeError(
            f"Unsupported image specification {type(image).__name__}"
        )

    def image(
        self,
        kind: ContentKind,
        content_id: ContentId,
        *,
        default_name: str,
    ) -> FrontendImage:
        presentation = self.presentation(kind, content_id)
        image = (
            presentation.image
            if presentation is not None
            else None
        )

        return self._frontend_image(
            kind,
            content_id,
            image=image,
            default_name=default_name,
            role='image',
        )

    def artifact_images(
        self,
        artifact_id: int,
        *,
        default_name: str,
    ) -> FrontendArtifactImages:
        presentation = self.presentation(
            'artifact',
            artifact_id,
        )
        image = self.image(
            'artifact',
            artifact_id,
            default_name=default_name,
        )

        if (presentation is None) or (presentation.overlay is None):
            overlay = image
        else:
            overlay = self._frontend_image(
                'artifact',
                artifact_id,
                image=presentation.overlay,
                default_name=default_name,
                role='overlay',
            )

        return FrontendArtifactImages(
            image=image,
            overlay_url=_frontend_image_url(
                overlay,
                'artifacts/overlays',
            ),
        )

    def enchantment_images(
        self,
        enchantment_id: str,
        *,
        default_name: str,
    ) -> FrontendEnchantmentImages:
        presentation = self.presentation(
            'enchantment',
            enchantment_id,
        )

        background = self.image(
            'enchantment',
            enchantment_id,
            default_name=default_name,
        )
        background_url = _frontend_image_url(
            background,
            'enchants/backgrounds',
        )

        if (presentation is None) or (presentation.overlay is None):
            overlay = self._frontend_image(
                'enchantment',
                enchantment_id,
                image=DEFAULT_ENCHANTMENT_OVERLAY_IMAGE,
                default_name=DEFAULT_ENCHANTMENT_OVERLAY_IMAGE.name,
                role='overlay',
            )
        else:
            overlay = self._frontend_image(
                'enchantment',
                enchantment_id,
                image=presentation.overlay,
                default_name=default_name,
                role='overlay',
            )
        overlay_url = _frontend_image_url(
            overlay,
            'enchants/overlays',
        )

        if (presentation is None) or (presentation.log is None):
            log_url = background_url
        else:
            log = self._frontend_image(
                'enchantment',
                enchantment_id,
                image=presentation.log,
                default_name=default_name,
                role='log',
            )
            log_url = _frontend_image_url(
                log,
                'enchants/logs',
            )

        return FrontendEnchantmentImages(
            asset_name=background.name,
            background_url=background_url,
            overlay_url=overlay_url,
            log_url=log_url,
        )

    def frontend_name(
        self,
        kind: ContentKind,
        content_id: ContentId,
        *,
        default_name: str,
    ) -> str:
        if kind == 'enchantment':
            return _enchantment_asset_name(default_name)

        return default_name

    def localization_keys(
        self,
        kind: ContentKind,
        content_id: ContentId,
    ) -> tuple[str, str]:
        if kind == 'card':
            return (
                f'card-name-{content_id}',
                f'card-{content_id}',
            )

        if kind == 'artifact':
            return (
                f'artifact-name-{content_id}',
                f'artifact-{content_id}',
            )

        if kind == 'soul':
            key = _kebab_case(str(content_id))
            return (
                f'soul-{key}',
                f'soul-{key}-desc',
            )

        if kind == 'enchantment':
            presentation = self._presentations[kind, content_id]
            key = _kebab_case(
                _enchantment_asset_name(presentation.text('en').name)
            )

            return (
                f'enchant-{key}',
                f'enchant-{key}-desc',
            )

        raise ValueError(f"Unsupported content kind {kind!r}")

    def localization_entries(
        self,
        locale: str,
    ) -> dict[str, str]:
        result = {}

        for presentation in self._presentations.values():
            text = presentation.text(locale)
            name_key, description_key = self.localization_keys(
                presentation.kind,
                presentation.content_id,
            )

            result[name_key] = text.name
            result[description_key] = text.description

        return result


CONTENT = ContentRegistry()
