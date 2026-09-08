from dataclasses import dataclass, field

from deltacards.engine.limits import RuntimeLimits


@dataclass(frozen=True, slots=True)
class ScriptedContentLimits:
    max_pack_bytes: int = 1 * 1024 * 1024
    max_entities: int = 128
    max_ir_nodes_per_entity: int = 512
    max_ir_nodes_per_pack: int = 16_384
    max_ir_depth: int = 48
    max_sequence_length: int = 64
    max_name_length: int = 80
    max_description_length: int = 4_096
    max_integer_magnitude: int = 10_000
    max_card_stat: int = 999
    max_counter: int = 999
    max_variables_per_entity: int = 64
    max_iteration_count: int = 128

    runtime_limits: RuntimeLimits = field(
        default_factory=lambda: RuntimeLimits(
            max_runtime_entities=2_000,
            max_recorded_results=20_000,
        )
    )

    def __post_init__(self) -> None:
        for name in (
            'max_pack_bytes',
            'max_entities',
            'max_ir_nodes_per_entity',
            'max_ir_nodes_per_pack',
            'max_ir_depth',
            'max_sequence_length',
            'max_name_length',
            'max_description_length',
            'max_integer_magnitude',
            'max_card_stat',
            'max_counter',
            'max_variables_per_entity',
            'max_iteration_count',
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


DEFAULT_SCRIPTED_CONTENT_LIMITS = ScriptedContentLimits()
