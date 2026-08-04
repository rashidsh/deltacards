from dataclasses import dataclass
from functools import cache

from deltacards.actions.results import (
    AbilityTriggeredResult,
    AttackDeclaredResult,
    CardDrawnResult,
    CardOverdrawnResult,
    CardPlayedResult,
    CardRevealedResult,
    EntityDamagedResult,
    MonsterKilledResult,
    MonsterSummonedResult,
    PlayerDefeatedResult,
    SpellCastResult,
)
from deltacards.engine.action_log import ActionLogRecord
from deltacards.model.enums import Ability, CardZone, PlayerId
from deltacards.model.snapshots import (
    ArtifactSnapshot,
    CardSnapshot,
    MonsterSnapshot,
    PlayerSnapshot,
    SoulSnapshot,
    SpellSnapshot,
)


@dataclass(frozen=True, slots=True)
class LogView:
    viewer_id: PlayerId | None


@dataclass(frozen=True, slots=True)
class RenderedLogLine:
    record_id: int
    group_id: int
    parent_id: int | None
    indent: int
    text: str


def can_view_card(snapshot: CardSnapshot, view: LogView) -> bool:
    if view.viewer_id is None:
        return False

    if snapshot.zone is not CardZone.HAND:
        return True

    if snapshot.controller_id == view.viewer_id:
        return True

    return False


def entity_name(snapshot) -> str:
    if isinstance(snapshot, PlayerSnapshot):
        return f"Player {snapshot.id.value}"

    if isinstance(snapshot, CardSnapshot):
        style_name = 'monster' if isinstance(snapshot, MonsterSnapshot) else 'spell'
        return f"[{snapshot.id}] [{style_name}]{snapshot.template.name}[/{style_name}]"

    if isinstance(snapshot, SoulSnapshot):
        style_name = f"soul-{snapshot.name.lower()}"
        return f"[{style_name}]{snapshot.name}[/{style_name}]"

    if isinstance(snapshot, ArtifactSnapshot):
        return snapshot.name

    raise TypeError


def visible_entity_name(snapshot, view: LogView) -> str:
    if isinstance(snapshot, CardSnapshot):
        if not can_view_card(snapshot, view):
            return "a card"

    return entity_name(snapshot)


class ActionLogFormatter:
    def __init__(self, view: LogView):
        self.view = view

    def _describe_result(self, result) -> str | None:
        if isinstance(result, CardRevealedResult):
            return f"{entity_name(result.card)} was revealed."

        if isinstance(result, CardDrawnResult):
            return f"Player {result.player_id.value} drew {visible_entity_name(result.card, self.view)}."

        if isinstance(result, CardOverdrawnResult):
            return f"Player {result.player_id.value} overdrew {entity_name(result.card)}"

        if isinstance(result, EntityDamagedResult):
            return (
                f"{entity_name(result.target)} took {result.amount} damage. "
                f"(HP {result.target.hp + result.amount} -> {result.target.hp})."
            )

        if isinstance(result, AttackDeclaredResult):
            attacker = entity_name(result.attacker)
            defender = entity_name(result.defender)
            return f"{attacker} attacked {defender}."

        if isinstance(result, MonsterSummonedResult):
            if result.target is not None:
                target_desc = f"Chosen target: {entity_name(result.target)}."
            else:
                target_desc = None

            # Monsters played from hand already have a `CardPlayedResult` logged,
            # but that result does not include the chosen target.
            if result.is_played:
                return target_desc

            desc = f"{entity_name(result.monster)} was summoned to Player {result.monster.controller_id}'s board."
            if target_desc:
                desc += " " + target_desc

            return desc

        if isinstance(result, SpellCastResult):
            if result.target is not None:
                target_desc = f"Chosen target: {entity_name(result.target)}."
            else:
                target_desc = None

            # Spells played from hand already have a `CardPlayedResult` logged,
            # but that result does not include the chosen target.
            if result.is_played:
                return target_desc

            desc = f"Player {result.player_id} cast {entity_name(result.card)}."
            if target_desc:
                desc += " " + target_desc

            return desc

        if isinstance(result, CardPlayedResult):
            return f"Player {result.player_id} played {entity_name(result.card)}."

        if isinstance(result, MonsterKilledResult):
            return f"{entity_name(result.monster)} died."

        if isinstance(result, PlayerDefeatedResult):
            return f"Player {result.player_id.value} was defeated."

        if isinstance(result, AbilityTriggeredResult):
            if (result.ability is Ability.MAGIC) and isinstance(result.entity, SpellSnapshot):
                return None

            ability_name = result.ability.value.title().replace('_', ' ')
            return f"[underline]{ability_name}[/underline] ability of {entity_name(result.entity)} was triggered."

        return None

    def _describe_results(self, record: ActionLogRecord) -> list[str]:
        lines: list[str] = []

        for result in record.display_results:
            line = self._describe_result(result)
            if line is not None:
                lines.append(line)

        return lines

    def describe_record(self, record: ActionLogRecord) -> list[str]:
        result_lines = self._describe_results(record)
        if result_lines:
            return result_lines

        return []

    def format_records(self, records: list[ActionLogRecord]) -> list[RenderedLogLine]:
        records_by_id = {record.id: record for record in records}

        descriptions = {}
        for record in records:
            texts = self.describe_record(record)
            if texts:
                descriptions[record.id] = texts

        visible_ids = descriptions.keys()

        @cache
        def visible_indent(record_id: int) -> int:
            record = records_by_id[record_id]
            parent = records_by_id.get(record.parent_id)

            if (parent is None) or (parent.group_id != record.group_id):
                return 0

            return visible_indent(parent.id) + (1 if (parent.id in visible_ids) else 0)

        return [
            RenderedLogLine(
                record_id=record.id,
                group_id=record.group_id,
                parent_id=record.parent_id,
                indent=visible_indent(record.id),
                text=text,
            )
            for record in records
            for text in descriptions.get(record.id, ())
        ]
