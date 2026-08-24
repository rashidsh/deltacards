from deltacards.dsl.api import *


@card(96)
class Punishment(Spell):
    targets = ENEMY_MONSTERS

    magic = TARGET.hit(4)


@card(97)
class Strafe(Spell):
    targets = ENEMY_MONSTERS

    adjacent_monsters: Var[TargetSelector] = Var(TargetSelector)
    hit_result: Var[StepResult] = Var(StepResult)

    magic = (
        SetVar(var=adjacent_monsters, value=ADJACENT(TARGET))
        >> TARGET.hit(7).store_result(hit_result).to(
            adjacent_monsters.hit(hit_result.excess_damage)
        )
    )


@card(98)
class UndynesSpears(Spell):
    spear_1: Var[TargetSelector] = Var(TargetSelector)
    spear_2: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(var=spear_1, value=GENERATE_CARD("Spear"))
        >> spear_1.summon()

        >> SetVar(var=spear_2, value=GENERATE_CARD("Spear"))
        >> spear_2.summon()

        >> Program(5).to(
            spear_1.set_stats(attack=5, hp=7)
            >> spear_2.set_stats(attack=5, hp=7)
        )

        >> spear_1.force_attack(ENEMY_MONSTERS >> MIN(ATTACK))
        >> spear_2.force_attack(ENEMY_MONSTERS >> MIN(ATTACK))
    )


@card(99)
class Reload(Spell):
    spell: Var[Card] = Var(Card)

    magic = ForEach(
        (
            HAND
            & IS_SPELL
            & NON_TOKEN
            & (TEMPLATE_ID != SELF.template_id)
        ),
        var=spell,
        effect=spell.set_status(LOOP, value=spell.status(LOOP) + 1)
    )


@card(100)
class Headshot(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.silence()
        >> TARGET.kill()
    )


@card(131)
class Energizer(Spell):
    magic = (
        ALLY_MONSTERS.buff(attack=+1)
        >> ENEMY_MONSTERS.hit(1)
    )


@card(181)
class MultiShot(Spell):
    _artifact = YOU.artifact("True Justice")

    magic = SELF.schedule_delay_effect()

    delay = (
        Check(YOU & HAS_ARTIFACT("True Justice")).to(
            While(
                (_artifact.counter > 0)
                & _artifact.active
                & (
                    (COUNT(ENEMY_MONSTERS) >= 1)
                    | (YOU.hp < OPPONENT.hp)
                ),
                _artifact.trigger_ability(Ability.TURN_END)
            ),
            else_=YOU.add_artifact(
                ARTIFACT_BY_NAME("True Justice")
            )
        )
        >> _artifact.update_artifact_counter(+6)
    )


@card(258)
class BlitzQuiz(Spell):
    magic = (
        YOU.choose(
            GENERATE_CARD("Trick Question") | GENERATE_CARD("Zap Cannon")
        ).to(
            CHOICE_SELECTED.to_hand()
        )
    )


@card(455)
class Powerhouse(Spell):
    magic = (
        DrawUpTo(2)
        >> HAND.buff(cost=-1)
    )


@card(463)
class TrickQuestion(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.hit(3)
        >> YOU.draw((DECK & IS_MONSTER).first())
    )


@card(464)
class ZapCannon(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.hit(3)
        >> YOU.draw((DECK & IS_SPELL & (TEMPLATE_NAME != "Blitz Quiz")).first())
    )


@card(487)
class RoyalJustice(Spell):
    generated_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=generated_cards,
            value=(
                (
                    SPELLS_CAST(player=YOU)
                    & NON_TOKEN
                    & OF_SOUL('justice')
                )
                >> AS_TEMPLATES(distinct=True)
                >> GENERATE_CARD()
            )
        )
        >> generated_cards.buff(cost=-1)
        >> generated_cards.to_hand()
    )


@card(700)
class Vasebreaker(Spell):
    targets = ALL_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)

    magic = TARGET.hit(2).store_result(hit_result).to(
        Check(hit_result.killed).to(
            GENERATE_CARD("Vase").summon()
        )
    )


@card(735)
class Judgement(Spell):
    magic = For(
        YOU.max_hp - YOU.hp,
        (ENEMY_MONSTERS >> RANDOM(1)).hit(1),
    )


@card(854)
class Dual(Spell):
    magic = (
        GENERATE_CARD("Quick Draw").to_hand()
        >> GENERATE_CARD("Quick Draw", controller=OPPONENT).to_hand()
    )


@card(855)
class QuickDraw(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.add_keyword(WANTED)
        >> TARGET.hit(3)
    )

    bullseye = YOU.draw_next()
