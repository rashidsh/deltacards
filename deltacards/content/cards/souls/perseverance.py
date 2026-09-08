from deltacards.dsl.api import *


@card(86)
class Worsening(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.buff(attack=-1, hp=-2)
        >> SELF.schedule_delay_effect()
    )

    delay = Check(
        (~SELF.is_generated) & TARGET.dead
    ).to(
        GENERATE_CARD("Worsening").to_hand()
    )


@card(87)
class Poison(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.add_keyword(KR)
        >> YOU.draw_next()
    )


@card(88)
class ButtercupTreat(Spell):
    targets = ALL_MONSTERS & NON_DT

    magic = (
        TARGET.set_stats(attack=1)
        >> SELF.schedule_delay_effect()
    )

    delay = (
        TARGET.silence()
        >> TARGET.add_keyword(KR)
        >> TARGET.add_keyword(CANDY)
    )


@card(89)
class PollutantGas(Spell):
    magic = For(2, GENERATE_CARD("Toxic Cloud").summon())


@card(90)
class Contamination(Spell):
    kill_targets: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=kill_targets,
            value=(ENEMY_MONSTERS & DAMAGED) >> RANDOM(2)
        )
        >> kill_targets.add_keyword(KR)
        >> kill_targets.kill()
    )


@card(134)
class SpiderWeb(Spell):
    targets = ENEMY_MONSTERS

    magic = (
        TARGET.add_keyword(KR)
        >> TARGET.buff(attack=-1, hp=-1)
        >> SELF.schedule_delay_effect()
    )

    delay = Check(TARGET.dead).to(
        For(3, GENERATE_CARD("Spider").summon())
    )


@card(183)
class Aftermath(Spell):
    magic = (
        (ENEMY_SLOTS & OCCUPIED_SLOT)
        >> RANDOM(2)
    ).enchant(
        ENCHANTMENT_BY_NAME("Scattering Dust")
    )


@card(261)
class Siphoning(Spell):
    targets = ALL_MONSTERS

    front_monster: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(var=front_monster, value=FRONT(TARGET))
        >> TARGET.buff(hp=-2).to(
            front_monster.buff(hp=+3)
            >> Check(TARGET.dead).to(
                GENERATE_CARD("Draft").to_deck()
            )
        )
    )


@card(460)
class WormInfusion(Spell):
    targets = ALLY_MONSTERS & NON_DT

    worm: Var[Card] = Var(Card)

    magic = (
        SetVar(var=worm, value=GENERATE_CARD("Worm"))
        >> worm.set_base_stats(
            attack=TARGET.attack,
            hp=TARGET.hp
        )
        >> TARGET.turn_into(worm)
    )


@card(484)
class RoyalPerseverance(Spell):
    magic = (
        (ENEMY_MONSTERS & HAS_KEYWORD(KR)).kill()
        >> ENEMY_MONSTERS.add_keyword(KR)
    )


@card(703)
class Proceed(Spell):
    targets = ALL_MONSTERS & NON_DT

    magic = (
        TARGET.silence()
        >> TARGET.force_attack(BOARD_OF(OPPONENT_OF(TARGET)))
    )


@card(738)
class Petrification(Spell):
    targets = ENEMY_MONSTERS

    magic = TARGET.kill().to(
        GENERATE_CARD(
            "Petrified Monster",
            controller=OPPONENT
        ).summon(controller=OPPONENT)
    )


@card(858)
class TrolleyProblem(Spell):
    magic = GENERATE_CARD("Fake Train").summon()
