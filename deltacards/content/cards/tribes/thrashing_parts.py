from deltacards.dsl.api import *


THRASHING_PART = HAS_TRIBE(Tribe.THRASHING_PART)


@card(689)
class LaserTopper(Monster):
    turn_end = SELF.kill().to(
        YOU.heal(3)
    )


@card(690)
class BoxedBody(Monster):
    dust = (ENEMY_MONSTERS >> MAX(HP)).hit(2)


@card(691)
class MobilityTracks(Monster):
    hand_count: Var[int] = Var(int)

    magic = (
        YOU.draw_next()
        >> SetVar(var=hand_count, value=COUNT(HAND))
        >> HAND.to_deck()
        >> For(
            hand_count,
            effect=YOU.draw_next()
        )
    )


@card(692)
class FailedDesign(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker.controller_id == self.controller_id:
            return None

        return SELF.buff(hp=-1)

    dust = GENERATE_CARD("Apoca Duck").summon()


@card(693)
class RoundDevices(Monster):
    magic = (ALL_MONSTERS & ~SELF).swap_stats()


@card(694)
class ToughBody(Monster):
    hit_result: Var[StepResult] = Var(StepResult)

    magic = SELF.schedule_delay_effect()

    delay = (
        (ENEMY_MONSTERS >> RANDOM(1)).hit(4).store_result(hit_result).to(
            OPPONENT.hit(hit_result.excess_damage)
        )
    )


@card(695)
class FlameOfLove(Monster):
    targets = ENEMY_MONSTERS

    magic = (
        TARGET.buff(attack=-3)
        >> ADJACENT(TARGET).buff(attack=-1)
    )
