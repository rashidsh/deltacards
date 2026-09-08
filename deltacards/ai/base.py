from abc import ABC, abstractmethod
from dataclasses import dataclass

from deltacards.engine.runner import (
    EngineUpdate,
    GameRunner,
    StepListener,
)
from deltacards.model.enums import PlayerId
from deltacards.model.requests import EngineInput, PendingRequest


class GameAI(ABC):
    @abstractmethod
    def choose_response(self, runner: GameRunner, request: PendingRequest) -> EngineInput:
        pass


@dataclass(slots=True)
class AIGameController:
    runner: GameRunner
    agents: dict[PlayerId, GameAI]

    def resolve_until_blocked(
        self,
        *,
        max_ai_inputs: int = 1_000,
        step_listener: StepListener | None = None,
        step_limit: int | None = None,
        terminate_on_step_limit: bool = False,
    ) -> EngineUpdate:
        all_results = []
        all_log_records = []
        total_steps = 0
        remaining_steps = step_limit

        def terminate(code: str) -> EngineUpdate:
            self.runner.game.terminate_for_resource_limit(code)
            return EngineUpdate(
                results=all_results,
                pending=(),
                game_over=True,
                log_records=all_log_records,
                steps=total_steps,
            )

        for _ in range(max_ai_inputs):
            if remaining_steps is not None and remaining_steps <= 0:
                if terminate_on_step_limit:
                    return terminate('resolution_steps')

                raise RuntimeError("Step limit reached (possible infinite loop).")

            update = self.runner.resolve_until_blocked(
                step_limit=(
                    self.runner.MAX_STEPS
                    if remaining_steps is None
                    else remaining_steps
                ),
                step_listener=step_listener,
                terminate_on_step_limit=terminate_on_step_limit,
            )
            all_results.extend(update.results)
            all_log_records.extend(update.log_records)
            total_steps += update.steps

            if remaining_steps is not None:
                remaining_steps -= update.steps

            if (
                update.game_over
                or any(
                    request.player_id not in self.agents
                    for request in update.pending
                )
            ):
                return EngineUpdate(
                    results=all_results,
                    pending=update.pending,
                    game_over=update.game_over,
                    log_records=all_log_records,
                    steps=total_steps,
                )

            for request in update.pending:
                ai = self.agents[request.player_id]
                response = ai.choose_response(self.runner, request)

                ok, reason = self.runner.provide_input(response)
                if not ok:
                    raise RuntimeError(
                        "AI produced a response rejected by runner: "
                        f"{reason}; request={request!r}; response={response!r}"
                    )

        if terminate_on_step_limit:
            return terminate('ai_inputs')

        raise RuntimeError("AI input limit reached (possible infinite loop).")
