from dataclasses import dataclass


class ResourceLimitError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(f"Game resource limit exceeded: {code}")
        self.code = code


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    max_runtime_entities: int
    max_recorded_results: int

    def __post_init__(self) -> None:
        for name in (
            'max_runtime_entities',
            'max_recorded_results',
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

    def restricted_by(self, other: 'RuntimeLimits') -> 'RuntimeLimits':
        return RuntimeLimits(
            max_runtime_entities=min(
                self.max_runtime_entities,
                other.max_runtime_entities,
            ),
            max_recorded_results=min(
                self.max_recorded_results,
                other.max_recorded_results,
            ),
        )
