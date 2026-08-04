from dataclasses import dataclass

from deltacards.actions.results import ActionResult
from deltacards.model.enums import PlayerId


@dataclass(slots=True)
class ActionLogRecord:
    id: int

    action_name: str
    results: tuple[ActionResult, ...]

    group_id: int
    parent_id: int | None
    depth: int

    source_id: PlayerId | int | None = None
    affected_ids: tuple[PlayerId | int, ...] = ()

    # `None` means that UI and action-log consumers should present the
    # ordinary engine results. An empty tuple intentionally presents nothing.
    presentation_results: tuple[ActionResult, ...] | None = None

    @property
    def display_results(self) -> tuple[ActionResult, ...]:
        if self.presentation_results is None:
            return self.results

        return self.presentation_results
