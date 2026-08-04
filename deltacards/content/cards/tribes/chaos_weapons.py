from deltacards.dsl.api import *


@card(445)
class Devilsknife(Spell):
    magic = (ENEMY_MONSTERS >> RANDOM(1)).kill()


@card(446)
class DiamondChaos(Spell):
    draw_result: Var[StepResult] = Var(StepResult)

    magic = For(
        3,
        effect=Check((COUNT(HAND) < MAX_HAND_SIZE) & (COUNT(DECK) > 0)).to(
            YOU.draw_next().store_result(draw_result).to(
                Buff(target=draw_result.card_id, cost=-2)
            )
        )
    )


@card(447)
class ClubChaos(Spell):
    magic = For(
        7,
        effect=Cast(
            card=DISCOVER(IS_SPELL, NON_TOKEN, COST <= 4),
            controller=YOU,
            effect_target='random'
        )
    )


@card(448)
class HeartChaos(Spell):
    magic = ALLIES.heal(7)


@card(449)
class SpadeChaos(Spell):
    magic = ENEMIES.hit(EMPTY_SLOTS(BOARD))


@card(715)
class Jevilstail(Spell):
    magic = (
        ALLY_MONSTERS.buff(attack=+1, hp=+2)
        >> (HAND & IS_MONSTER).buff(attack=+1, hp=+1)
    )
