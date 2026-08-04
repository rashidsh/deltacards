from deltacards.dsl.api import *


@card(66)
class WillToFight(Spell):
    _effect = NEXT_LOST_SOUL.trigger_ability(DUST)

    magic = _effect >> SELF.schedule_delay_effect()
    delay = _effect


@card(67)
class Resurrection(Spell):
    generated_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (DUSTPILE & IS_MONSTER & NON_GENERATED) >> RANDOM(3)
    ).to(
        SetVar(var=generated_card, value=CHOICE_SELECTED >> COPY())
        >> CHOICE_SELECTED.erase()
        >> generated_card.to_hand()
    )


@card(68)
class AnotherChance(Spell):
    targets = ALLY_MONSTERS & NON_DT

    copied_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=copied_card, value=TARGET >> COPY())
        >> TARGET.kill().to(
            SELF.schedule_delay_effect()
        )
    )

    delay = (
        copied_card.buff(attack=-2, hp=-2, min_hp=1)
        >> copied_card.summon()
    )


@card(69)
class StarBlazing(Spell):
    erased_monsters: Var[TargetSelector] = Var(TargetSelector)
    erased_count: Var[int] = Var(int)
    not_summoned_count: Var[int] = Var(int)

    star_1: Var[Card] = Var(Card)
    star_2: Var[Card] = Var(Card)
    star_3: Var[Card] = Var(Card)
    star_4: Var[Card] = Var(Card)
    star_5: Var[Card] = Var(Card)

    _stars = star_1 | star_2 | star_3 | star_4 | star_5

    magic = (
        SetVar(
            var=erased_monsters,
            value=(
                DUSTPILE
                & IS_MONSTER
                & ~GENERATED_BY(SELF)
            ) >> RANDOM(15),
        )
        >> SetVar(var=erased_count, value=COUNT(erased_monsters))
        >> erased_monsters.erase()

        >> Check(erased_count >= 3).to(
            SetVar(var=star_1, value=GENERATE_CARD("Star"))
            >> star_1.summon()
        )
        >> Check(erased_count >= 6).to(
            SetVar(var=star_2, value=GENERATE_CARD("Star"))
            >> star_2.summon()
        )
        >> Check(erased_count >= 9).to(
            SetVar(var=star_3, value=GENERATE_CARD("Star"))
            >> star_3.summon()
        )
        >> Check(erased_count >= 12).to(
            SetVar(var=star_4, value=GENERATE_CARD("Star"))
            >> star_4.summon()
        )
        >> Check(erased_count >= 15).to(
            SetVar(var=star_5, value=GENERATE_CARD("Star"))
            >> star_5.summon()
        )

        >> SetVar(
            var=not_summoned_count,
            value=(erased_count // 3) - COUNT(_stars & BOARD),
        )
        >> (_stars & BOARD).buff(attack=not_summoned_count, hp=not_summoned_count)
    )


@card(70)
class HyperGoner(Spell):
    # TODO update kill order
    targets = ENEMY_MONSTERS

    magic = (ALL_MONSTERS & ~TARGET).kill()


@card(129)
class Knife(Spell):
    targets = ENEMY_MONSTERS

    kill_result: Var[StepResult] = Var(StepResult)

    magic = (
        TARGET.kill().store_result(kill_result).to(
            YOU.hit(kill_result.monster.cost)
        )
    )


@card(179)
class LastDream(Spell):
    magic = (
        ALLY_MONSTERS.buff(attack=+1, hp=+1)
        >> Check(YOU.hp == 1).to(
            ENEMY_MONSTERS.kill()
            >> YOU.heal(YOU.max_hp)
        )
    )


@card(256)
class SoulDrain(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.hit(3)
        >> SELF.schedule_delay_effect()
    )

    delay = (LOOP_COPY & HAND).erase().to(
        YOU.heal(4)
    )


@card(453)
class CallOfTheGrave(Spell):
    lost_soul: Var[Card] = Var(Card)
    save_counters: Var[int] = Var(int)

    _artifact = YOU.artifact("Save")

    magic = (
        SetVar(var=lost_soul, value=NEXT_LOST_SOUL)
        >> lost_soul.add_keyword(HASTE)
        >> lost_soul.summon(attack=1, hp=1)
        >> Check(_artifact).to(
            Program(2).to(
                SetVar(var=save_counters, value=_artifact.counter)
                >> _artifact.update_artifact_counter(-save_counters)
                >> lost_soul.buff(
                    attack=save_counters // 4,
                    hp=save_counters // 4,
                )
            )
        )
    )


@card(483)
class RoyalDetermination(Spell):
    monster_count: Var[int] = Var(int)
    lost_soul: Var[Card] = Var(Card)

    magic = (
        SetVar(var=monster_count, value=COUNT(DUSTPILE & IS_MONSTER))
        >> DUSTPILE.erase()
        >> For(
            monster_count // 7,
            effect=SetVar(var=lost_soul, value=NEXT_LOST_SOUL)
            >> lost_soul.add_keyword(HASTE)
            >> lost_soul.add_keyword(TAUNT)
            >> lost_soul.summon()
        )
    )


@card(702)
class CallForHelp(Spell):
    copies: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=copies,
            value=(
                MONSTERS_DIED(
                    controller=OPPONENT,
                    scope=THIS_TURN,
                )
                >> AS_CARDS()
                >> COPY()
            )
        )
        >> copies.summon()
    )


@card(734)
class ControlWire(Spell):
    magic = (
        YOU.choose(OPPONENT_HAND & IS_MONSTER & NON_DT).to(
            (CHOICE_SELECTED >> EXACT_COPY()).to_hand()
        )
    )


@card(856)
class Reminisce(Spell):
    generated_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (
            DUSTPILE
            & IS_MONSTER
            & NON_TOKEN
            & (COST <= 9)
        ) >> RANDOM(3)
    ).to(
        SetVar(var=generated_card, value=CHOICE_SELECTED >> COPY())
        >> generated_card.add_keyword(HASTE)
        >> generated_card.summon()
        >> CHOICE_SELECTED.erase()
    )
