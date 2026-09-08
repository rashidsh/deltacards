from dataclasses import dataclass
from typing import Any, Mapping

from deltacards.actions.results import ActionResult
from deltacards.dsl.core import TargetSelector
from deltacards.dsl.vars import Var
from deltacards.model.artifacts import Artifact
from deltacards.model.cards import Card, Monster, Spell
from deltacards.model.enchantments import Enchantment
from deltacards.model.entity import Entity, on_event
from deltacards.model.enums import Ability


@dataclass(frozen=True, slots=True)
class CompiledReaction:
    result_type: type[ActionResult]
    condition: Any
    effect: Any


@dataclass(frozen=True, slots=True)
class CompiledProgram:
    targets: TargetSelector | None
    need: Any | None
    abilities: Mapping[Ability, Any]
    variables: Mapping[str, Var]
    reactions: tuple[CompiledReaction, ...]


@dataclass(frozen=True, slots=True)
class ScriptedDefinition:
    content_id: str
    kind: str
    program: CompiledProgram


class ScriptedMonster(Monster):
    scripted_definition: ScriptedDefinition


class ScriptedSpell(Spell):
    scripted_definition: ScriptedDefinition


class ScriptedArtifact(Artifact):
    scripted_definition: ScriptedDefinition


class ScriptedEnchantment(Enchantment):
    scripted_definition: ScriptedDefinition


def make_scripted_type(
    base: type[Entity],
    definition: ScriptedDefinition,
    *,
    attributes: dict[str, Any] | None = None,
) -> type[Entity]:
    class_attributes = dict(attributes or {})
    class_attributes.update({
        '__module__': __name__,
        'scripted_definition': definition,
    })

    for ability, effect in definition.program.abilities.items():
        class_attributes[ability.value] = effect

    if issubclass(base, Card):
        class_attributes['targets'] = definition.program.targets
        if definition.program.need is not None:
            class_attributes['need'] = definition.program.need

    for index, variable in enumerate(definition.program.variables.values()):
        class_attributes[f'_scripted_variable_{index}'] = variable

    for index, reaction in enumerate(definition.program.reactions):
        class_attributes[f'_scripted_reaction_{index}'] = on_event(
            reaction.result_type,
            effect=reaction.effect,
            condition=reaction.condition,
        )

    class_name = f"Scripted{definition.kind.title()}_{definition.content_id.replace('-', '')}"
    return type(class_name, (base,), class_attributes)
