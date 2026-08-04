from deltacards.dsl.api import *


@card(76)
class Strength(Spell):
    magic = ALLY_MONSTERS.buff(attack=+1, hp=+1)


@card(77)
class Assault(Spell):
    targets = ALLY_MONSTERS

    magic = TARGET.add_keyword(HASTE)


@card(78)
class Rage(Spell):
    targets = ALLY_MONSTERS

    magic = (
        FRONT(TARGET).hit(TARGET.attack)
        >> TARGET.buff(attack=+1, hp=+1)
    )


@card(79)
class Penetration(Spell):
    targets = ALL_MONSTERS

    magic = TARGET.silence()


@card(80)
class RoyalSignup(Spell):
    other_card: Var[Card] = Var(Card)

    targets = HAND

    magic = ForEach(
            HAND & ~TARGET,
            var=other_card,
            effect=other_card.turn_into(GENERATE_CARD("Draft"))
        )


@card(128)
class FroggitTrio(Spell):
    frog_1: Var[Card] = Var(Card)
    frog_2: Var[Card] = Var(Card)
    reward_frog: Var[Card] = Var(Card)

    magic = (
        SetVar(var=frog_1, value=GENERATE_CARD("Froggit"))
        >> frog_1.add_keyword(HASTE)
        >> frog_1.summon()

        >> SetVar(var=frog_2, value=GENERATE_CARD("Froggit"))
        >> frog_2.add_keyword(HASTE)
        >> frog_2.summon()

        >> SELF.schedule_delay_effect()
    )

    delay = Check(
        frog_1.dead & frog_2.dead
    ).to(
        SetVar(var=reward_frog, value=GENERATE_CARD("Froggit"))
        >> reward_frog.set_stats(cost=0)
        >> reward_frog.add_keyword(HASTE)
        >> reward_frog.to_hand()
    )


@card(178)
class Overheat(Spell):
    targets = ALLY_MONSTERS

    kill_result: Var[StepResult] = Var(StepResult)

    magic = (
        TARGET.kill().store_result(kill_result).to(
            ENEMY_MONSTERS.hit(kill_result.monster.attack)
        )
    )


@card(255)
class Overgrowth(Spell):
    magic = (
        (
            (BOARD | HAND | DECK)
            & IS_MONSTER
            & GENERATED
        ).buff(attack=+1, hp=+1)
        >> YOU.draw_next()
    )


@card(452)
class Recruitment(Spell):
    magic = YOU.choose(
        (
            CARD_LIBRARY
            & IS_MONSTER
            & (RARITY <= EPIC)
            & (COST >= 4)
            & (COST <= 5)
        )
        >> RANDOM(5)
        >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.buff(hp=+1)
        >> CHOICE_SELECTED.to_hand()
    )


@card(454)
class Acceleration(Spell):
    targets = HAND

    magic = (
        TARGET.erase()
        >> (YOU.draw_next() * 3)
    )


@card(482)
class RoyalBravery(Spell):
    draw_result: Var[StepResult] = Var(StepResult)

    magic = (
        HAND.to_deck() >> For(
            5,
            effect=YOU.draw_next().store_result(draw_result).to(
                Buff(target=draw_result.card_id, cost=-1)
            )
        )
    )


@card(705)
class KnightsShield(Spell):
    targets = ALLY_MONSTERS

    magic = (
        TARGET.add_keyword(TAUNT)
        >> TARGET.buff(hp=EMPTY_SLOTS(BOARD))
    )


@card(733)
class DuckOff(Spell):
    magic = (
        GENERATE_CARD("Apoca Duck").summon()
        >> GENERATE_CARD("Apoca Duck").to_hand()
        >> Program(3).to(
            GENERATE_CARD("Apoca Duck").summon()
        )
    )


@card(857)
class Sandstorm(Spell):
    magic = For(
        COUNT(
            CARDS_PLAYED(player=YOU, scope=THIS_TURN)
            & (COST >= 1)
            & (CARD_ID != SELF.id)
        ),
        effect=ENEMY_MONSTERS.hit(1)
    )
