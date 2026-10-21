from collections.abc import Mapping

from deltacards.model.enums import CardKeyword, CardStatusId


NEGATIVE_KEYWORDS = (
    CardKeyword.KR
    | CardKeyword.DISARMED
    | CardKeyword.SILENCED
    | CardKeyword.WANTED
)

NEGATIVE_STATUS_IDS = (
    CardStatusId.PARALYZED,
    CardStatusId.MOLD_SPORE,
)


def card_has_negative_effects(
    *,
    cost_buff: int,
    attack_buff: int,
    max_hp_buff: int,
    keywords: CardKeyword,
    statuses: Mapping[CardStatusId, int],
) -> bool:
    if cost_buff > 0:
        return True

    if attack_buff < 0 or max_hp_buff < 0:
        return True

    if keywords & NEGATIVE_KEYWORDS:
        return True

    return (
        CardStatusId.MOLD_SPORE in statuses
        or any(
            statuses.get(status_id, 0) > 0
            for status_id in NEGATIVE_STATUS_IDS
            if status_id is not CardStatusId.MOLD_SPORE
        )
    )
