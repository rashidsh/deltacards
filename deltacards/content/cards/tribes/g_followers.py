from deltacards.dsl.api import *


G_FOLLOWER = HAS_TRIBE(Tribe.G_FOLLOWER)
NOT_ALL = ~HAS_TRIBE(Tribe.ALL)


@card(118)
class GFollower1(Monster):
    magic = YOU.draw(
        (DECK & HAS_ABILITY(SYNERGY)).first()
    )


@card(119)
class GFollower2(Monster):
    synergy = GENERATE_CARD("G Follower 2").summon()


@card(120)
class GFollower3(Monster):
    g_follower_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = Check(~SYNERGY_TRIGGERED).to(
        SetVar(
            var=g_follower_cards,
            value=(DISCOVER(G_FOLLOWER, NOT_ALL, n=2))
        )
        >> YOU.choose(g_follower_cards).to(
            CHOICE_SELECTED.to_hand()
        )
    )

    synergy = (
        SetVar(
            var=g_follower_cards,
            value=(DISCOVER(G_FOLLOWER, NOT_ALL, n=2))
        )
        >> g_follower_cards.buff(cost=-1)
        >> g_follower_cards.to_hand()
    )


@card(121)
class GonerKid(Monster):
    magic = Check(~SYNERGY_TRIGGERED).to(
        ((ALL_MONSTERS & ~SELF) >> RANDOM(1)).kill()
    )

    synergy = (
        (ENEMY_MONSTERS >> RANDOM(1)).kill()
    )


@card(177)
class Redacted(Monster):
    targets = ENEMY_MONSTERS

    magic = TARGET.buff(attack=-2, hp=-2)

    synergy = SELF.add_keyword(HASTE)


@card(415)
class GonerClam(Monster):
    targets = ALL_PLAYERS | ALL_MONSTERS

    magic = TARGET.heal(3)

    synergy = (ALLY_MONSTERS & G_FOLLOWER & ~SELF).buff(attack=+1, hp=+1)
