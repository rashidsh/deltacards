from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deltacards.content.registry import ContentKind, ContentPresentation
    from deltacards.model.templates import CardTemplate


_REGISTRATION_ATTRIBUTE = '__content_registration__'


@dataclass(frozen=True, slots=True)
class ContentRegistration:
    kind: 'ContentKind'
    content_id: int | str
    implementation: type
    template: 'CardTemplate | None' = None
    presentation: 'ContentPresentation | None' = None


def attach_registration(class_: type, registration: ContentRegistration) -> type:
    existing = class_.__dict__.get(_REGISTRATION_ATTRIBUTE)
    if existing is not None:
        raise ValueError(
            f"{class_.__module__}.{class_.__qualname__} already has a content registration"
        )

    if registration.implementation is not class_:
        raise ValueError("Content registration implementation does not match the decorated class")

    setattr(class_, _REGISTRATION_ATTRIBUTE, registration)
    return class_


def registration_of(class_: type) -> ContentRegistration | None:
    registration = class_.__dict__.get(_REGISTRATION_ATTRIBUTE)
    if registration is None:
        return None

    if not isinstance(registration, ContentRegistration):
        raise TypeError(
            f"{class_.__module__}.{class_.__qualname__} has invalid content registration metadata"
        )

    return registration


def registrations_from_module(module: ModuleType) -> tuple[ContentRegistration, ...]:
    registrations = []
    seen_classes: set[int] = set()

    for value in module.__dict__.values():
        if not isinstance(value, type):
            continue
        if value.__module__ != module.__name__:
            continue
        if id(value) in seen_classes:
            continue

        registration = registration_of(value)
        if registration is None:
            continue

        seen_classes.add(id(value))
        registrations.append(registration)

    return tuple(sorted(
        registrations,
        key=lambda item: (item.kind, str(item.content_id), item.implementation.__qualname__),
    ))
