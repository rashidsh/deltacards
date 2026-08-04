from deltacards.dsl.api import *


PIECE = HAS_TRIBE(Tribe.PIECE)

PONMAN = TEMPLATE_NAME == "Ponman"


@card(275)
class MisterSociety(Monster):
    magic = YOU.choose(
        HAND
        & PIECE
        & NON_TOKEN
        & (TEMPLATE_ID != SELF.template_id)
    ).to(
        SwitchPiece(
            left=(CHOICE_SELECTED >> COPY()).to_hand(),
            right=For(
                2,
                effect=(CHOICE_SELECTED >> COPY()).to_deck()
            )
        )
    )


@card(312)
class Ponman(Monster):
    magic = SwitchPiece(
        left=SELF.buff(hp=+2),
        right=YOU.heal(1)
    )


@card(313)
class PonmanStatue(Monster):
    magic = Check(
        COUNT(DUSTPILE & PIECE & NON_TOKEN) >= 18
    ).to(
        GENERATE_CARD("Ponqueen").to_hand()
    )


@card(394)
class MisterElegance(Monster):
    copied_card: Var[Card] = Var(Card)

    magic = SwitchPiece(
        left=(
            SELF.buff(attack=+1, hp=+1)
            >> SELF.add_keyword(ARMOR)
        ),
        right=(
            SetVar(var=copied_card, value=SELF >> COPY())
            >> copied_card.add_keyword(HASTE)
            >> copied_card.summon()
        )
    )


@card(434)
class DarkPonman(Monster):
    magic = SwitchPiece(
        left=For(
            3,
            effect=GENERATE_CARD("Ponman").to_hand()
        ),
        right=((HAND | BOARD) & PONMAN).buff(attack=+1, hp=+1)
    )


@card(480)
class Chessboard(Monster):
    summon_result: Var[StepResult] = Var(StepResult)

    magic = (
        For(
            COUNT(DUSTPILE & PIECE) // 3,
            effect=GENERATE_CARD("Ponman").summon().store_result(summon_result).to(
                TriggerAbility(target=summon_result.monster_id, ability=MAGIC)
            )
        )
    )


@card(727)
class MisterRuckus(Monster):
    targets = ALL_MONSTERS

    magic = SwitchPiece(
        left=TARGET.set_stats(attack=3, hp=3),
        right=TARGET.hit(3)
    )


@card(728)
class Ponqueen(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = (
        YOU.add_artifact(ARTIFACT_BY_NAME("Endgame"))
        >> Check(COUNT(DUSTPILE & PIECE) >= 18).to(
            (DUSTPILE & PIECE)[:18].erase()
            >> For(
                EMPTY_SLOTS(HAND),
                (
                    SetVar(var=generated_card, value=GENERATE_CARD("Ponman"))
                    >> generated_card.buff(attack=+3)
                    >> generated_card.set_status(DODGE, value=1)
                    >> generated_card.to_hand()
                )
            )
        )
    )
