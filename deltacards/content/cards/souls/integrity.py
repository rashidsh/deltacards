from deltacards.dsl.api import *


@card(81)
class Fortune(Spell):
    magic = ALL_PLAYERS.earn_gold(1)


@card(82)
class MercenaryHire(Spell):
    royal_guard_template: Var[CardTemplate] = Var(CardTemplate)
    royal_guard_card: Var[Card] = Var(Card)

    magic = ForEach(
        (
            CARD_LIBRARY
            & IS_MONSTER
            & HAS_TRIBE(Tribe.ROYAL_GUARD)
            & ~HAS_TRIBE(Tribe.ALL)
            & (COST == 9)
        ),
        var=royal_guard_template,
        effect=(
            SetVar(
                var=royal_guard_card,
                value=royal_guard_template >> GENERATE_CARD(),
            )
            >> royal_guard_card.set_base_stats(
                attack=royal_guard_card.base.attack - 4,
                hp=royal_guard_card.base.hp - 4,
            )
            >> royal_guard_card.summon()
        )
    )


@card(83)
class Shopping(Spell):
    magic = YOU.draw(
        (DECK & (COST <= 5)).first()
    ) * 3


@card(84)
class Expulsion(Spell):
    targets = ENEMY_MONSTERS

    magic = TARGET.to_deck(pos='top')


@card(85)
class Cloning(Spell):
    targets = ALL_MONSTERS & NON_DT

    copied_monster: Var[Card] = Var(Card)

    magic = (
        SetVar(var=copied_monster, value=TARGET >> COPY())
        >> copied_monster.summon(attack=3, hp=3).to(
            copied_monster.add_keyword(HASTE)
        )
    )


@card(130)
class Investment(Spell):
    magic = YOU.choose(
        DECK >> RANDOM(3)
    ).to(
        (CHOICE_SELECTED | CHOICE_NOT_SELECTED).buff(cost=-1)
        >> YOU.draw(CHOICE_SELECTED)
    )


@card(180)
class Inflation(Spell):
    magic = (
        YOU.add_artifact(ARTIFACT_BY_NAME("Economics"))
        >> YOU.artifact("Economics").update_artifact_counter(+6)
    )


@card(257)
class GoldenHit(Spell):
    targets = ENEMY_MONSTERS

    spend_result: Var[StepResult] = Var(StepResult)
    hit_result: Var[StepResult] = Var(StepResult)

    magic = YOU.spend_gold(
        amount=YOU.gold,
        allow_partial=True
    ).store_result(spend_result).to(
        TARGET.hit(spend_result.amount).store_result(hit_result).to(
            YOU.earn_gold(hit_result.excess_damage)
        )
    )


@card(458)
class Carousel(Spell):
    monster: Var[Card] = Var(Card)
    hit_result: Var[StepResult] = Var(StepResult)
    wave_kills: Var[int] = Var(int, default=0)

    _wave = (
        SetVar(var=wave_kills, value=0)
        >> ForEach(
            ALL_MONSTERS,
            var=monster,
            effect=monster.hit(1).store_result(hit_result).to(
                Check(hit_result.killed).to(
                    SetVar(var=wave_kills, value=wave_kills + 1)
                )
            ),
        )
    )

    magic = (
        _wave
        >> While(
            wave_kills > 0,
            _wave
        )
    )


@card(486)
class RoyalIntegrity(Spell):
    targets = ALL_MONSTERS & (TEMPLATE_NAME != "Alphys")

    copied_monster: Var[Card] = Var(Card)

    magic = (
        SetVar(var=copied_monster, value=TARGET >> EXACT_COPY())
        >> Check(
            (TARGET.rarity == CardRarity.LEGENDARY)
            | (TARGET.rarity == CardRarity.DETERMINATION)
        ).to(
            copied_monster.buff(cost=+2)
        )
        >> copied_monster.to_hand()
    )


@card(699)
class Wereform(Spell):
    targets = ALLY_MONSTERS & NON_DT

    werewire: Var[Card] = Var(Card)

    magic = (
        SetVar(var=werewire, value=GENERATE_CARD("Werewire"))
        >> werewire.summon().to(
            werewire.catch(TARGET)
        )
    )


@card(732)
class SillyStrings(Spell):
    targets = ENEMY_MONSTERS & NON_DT

    copied_monster: Var[Card] = Var(Card)

    magic = (
        SetVar(var=copied_monster, value=TARGET >> COPY())
        >> TARGET.kill().to(
            copied_monster.set_stats(cost=1)
            >> copied_monster.to_deck(pos='top')
        )
    )


@card(827)
class Lasso(Spell):
    chosen_monster: Var[Card] = Var(Card)

    magic = (
        SetVar(
            var=chosen_monster,
            value=(OPPONENT_HAND & IS_MONSTER) >> MIN(COST),
        )
        >> chosen_monster.summon(controller=OPPONENT).to(
            chosen_monster.paralyze()
            >> chosen_monster.add_keyword(WANTED)
        )
    )
