from deltacards.dsl.api import *


SNAIL = HAS_TRIBE(Tribe.SNAIL)


@card(222)
class BlueSnail(Monster):
    magic = ((DECK & SNAIL) >> RANDOM(1)).buff(cost=-1)


@card(223)
class YellowSnail(Monster):
    magic = (ALLY_MONSTERS & SNAIL & ~SELF).buff(hp=+1)


@card(224)
class RedSnail(Monster):
    magic = (ALLY_MONSTERS & SNAIL & ~SELF).buff(attack=1)


@card(492)
class BurningSnail(Monster):
    magic = SELF.buff(attack=COUNT(ADJACENT(SELF) & SNAIL))


@card(496)
class BusinessSnail(Monster):
    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_tribe(Tribe.SNAIL):
            return None

        return YOU.draw_next()
