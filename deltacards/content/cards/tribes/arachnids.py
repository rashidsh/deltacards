from deltacards.dsl.api import *


ARACHNID = HAS_TRIBE(Tribe.ARACHNID)


@card(55)
class Muffet(Monster):
    magic = SELF.schedule_delay_effect()

    delay = (
        GENERATE_CARD("Spider Donut").to_hand()
        >> GENERATE_CARD("Spider Croissant").to_deck()
    )

    turn_end = GENERATE_CARD("Spider Donut").to_hand()


@card(103)
class MuffetsPet(Monster):
    targets = ENEMY_MONSTERS

    magic = (
        TARGET.buff(attack=-2, min_attack=0)
        >> Check(TARGET.attack == 0).to(
            TARGET.kill()
        )
    )


@card(473)
class SpiderReporter(Monster):
    dust = GENERATE_CARD("Spider Croissant").to_deck()


@card(474)
class SpiderSign(Monster):
    _effect = (DECK & TOKEN & ARACHNID).first().summon()

    magic = _effect
    turn_start = _effect

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_tribe(Tribe.ARACHNID):
            return None

        return SELF.buff(attack=+1)


@card(475)
class SpiderDonut(Monster):
    magic = SELF.schedule_delay_effect()

    delay = SELF.heal(3) >> YOU.heal(3)


@card(476)
class SpiderCroissant(Monster):
    dust = GENERATE_CARD("Spider").summon()


@card(478)
class SpiderBakery(Monster):
    magic = Check(~SYNERGY_TRIGGERED).to(
        GENERATE_CARD("Spider").to_hand()
        >> GENERATE_CARD("Spider").to_deck()
    )

    synergy = (
        GENERATE_CARD("Spider Donut").to_hand()
        >> GENERATE_CARD("Spider Croissant").to_deck()
    )


@card(744)
class HangingSpider(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(
        MONSTERS_DIED(controller=YOU)
        & (MONSTER_ID == SELF.id)
        & KILLED_BY_MONSTER
    ).to(
        GENERATE_CARD("Spider Croissant").summon()
        >> GENERATE_CARD("Spider Donut").to_hand()
    )


@card(845)
class SpiderWorkers(Monster):
    magic = Check(~SYNERGY_TRIGGERED).to(
        GENERATE_CARD("Spider").summon()
    )

    synergy = GENERATE_CARD("Spider Croissant").summon()
