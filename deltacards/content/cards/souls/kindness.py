from deltacards.dsl.api import *


@card(91)
class HealCard(Spell):
    targets = ALLIES | ENEMIES

    magic = (
        TARGET.heal(3)
        >> Check(TARGET & ALL_PLAYERS).to(
            YOU.draw_next(),
            else_=TARGET.remove_negative_effects()
        )
    )


@card(92)
class ForceOfNature(Spell):
    targets = ALLIES | ENEMIES

    hit_result: Var[StepResult] = Var(StepResult)

    magic = TARGET.hit(3).store_result(hit_result).to(
        ALLIES.buff(hp=hit_result.excess_damage)
    )


@card(93)
class Longevity(Spell):
    magic = (
        ALLY_MONSTERS.buff(hp=+1)
        >> YOU.draw_next()
    )


@card(94)
class Feast(Spell):
    magic = (
        (ALLY_MONSTERS & (HP <= 4)).buff(hp=+2)
        >> SELF.schedule_delay_effect()
    )

    delay = (ALLY_MONSTERS & (ATTACK <= 4)).buff(attack=+2)


@card(95)
class TestOfWill(Spell):
    monster: Var[Card] = Var(Monster)

    magic = ForEach(
        ALL_MONSTERS,
        var=monster,
        effect=monster.hit(monster.attack)
    )


@card(132)
class Pie(Spell):
    targets = ALL_MONSTERS

    magic = TARGET.heal(TARGET.max_hp - TARGET.hp)


@card(184)
class Soothing(Spell):
    targets = ALL_MONSTERS

    magic = TARGET.set_stats(attack=3, hp=2)


@card(259)
class Octofriend(Spell):
    targets = ALLY_MONSTERS

    left_tentacle: Var[Card] = Var(Monster)
    right_tentacle: Var[Card] = Var(Monster)

    magic = (
        TARGET.buff(attack=+1, hp=+1)

        >> SetVar(var=left_tentacle, value=GENERATE_CARD("Left Tentacle"))
        >> left_tentacle.set_stats(cost=1)
        >> left_tentacle.to_hand()

        >> SetVar(var=right_tentacle, value=GENERATE_CARD("Right Tentacle"))
        >> right_tentacle.set_stats(cost=1)
        >> right_tentacle.to_hand()
    )


@card(456)
class Campfire(Spell):
    magic = (
        For(
            4,
            ((ALLY_MONSTERS & DAMAGED) >> RANDOM(1)).heal(1)
        )
        >> ((HAND & IS_MONSTER) >> RANDOM(4)).buff(attack=+1, hp=+1)
    )


@card(481)
class RoyalKindness(Spell):
    affected_monsters: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(var=affected_monsters, value=ALLY_MONSTERS)
        >> affected_monsters.add_keyword(HASTE)
        >> affected_monsters.add_keyword(INVULNERABLE)
        >> SELF.schedule_delay_effect()
    )

    delay = affected_monsters.remove_keyword(INVULNERABLE)


@card(704)
class PezzaTime(Spell):
    targets = ALLY_MONSTERS & DAMAGED & NON_DT

    copied_monster: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(var=copied_monster, value=TARGET >> COPY())
        >> copied_monster.set_stats(hp=TARGET.hp)
        >> copied_monster.buff(cost=TARGET.hp_missing * -1)
        >> copied_monster.to_hand()
    )


@card(731)
class UltimateHeal(Spell):
    draw_result: Var[StepResult] = Var(StepResult)

    magic = (
        For(
            3,
            YOU.draw(card=(DECK & IS_MONSTER).first()).store_result(draw_result).to(
                Buff(target=draw_result.card_id, cost=-1)
            )
        )
    )


@card(860)
class Bounty(Spell):
    wanted_monsters: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(var=wanted_monsters, value=ENEMY_MONSTERS >> RANDOM(2))
        >> wanted_monsters.add_keyword(WANTED)
        >> SELF.schedule_delay_effect()
    )

    delay = Check(
        COUNT(wanted_monsters & DEAD) == 2
    ).to(
        ((HAND & IS_MONSTER) >> RANDOM(4)).buff(attack=+1, hp=+1)
    )
