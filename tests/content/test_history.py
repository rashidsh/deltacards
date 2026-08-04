from deltacards.dsl.api import *

from ..card_templates import synthetic_card
from ..rig import TestRig


@synthetic_card(
    598,
    cost=1,
)
class Gemstone(Spell):
    # Deal 1 DMG.
    targets = ALL_PLAYERS | ALL_MONSTERS

    magic = TARGET.hit(1)


@synthetic_card(
    548,
    cost=1,
    attack=1,
    hp=4,
)
class MagicCrystal(Monster):
    # Magic: Cast 4 Gemstones on random alive enemy monsters.
    # If you spent gold on spells last turn, add a Crystal Downpour to your hand.
    magic = For(
        4,
        effect=Cast(
            card=GENERATE_CARD("Gemstone"),
            controller=YOU,
            effect_target=ENEMY_MONSTERS >> RANDOM(1)
        )
    ) >> Check(
        SPENT_GOLD_ON_SPELLS_LAST_TURN
    ).to(
        GENERATE_CARD("Crystal Downpour").to_hand()
    )


def test_magic_crystal():
    rig = TestRig.create(p1_deck=[548], p2_deck=[1, 1])

    rig.p1.end_turn()

    defender_1 = rig.p2.hand[0]
    defender_2 = rig.p2.hand[1]
    rig.p2.play_monster(defender_1)
    rig.p2.play_monster(defender_2)
    defender_1.buff(hp=+1)
    defender_2.buff(hp=+1)
    rig.p2.end_turn()

    rig.p1.play_monster(rig.p1.hand[0])
    assert sum(1 for m in rig.p2.board if m) == 2
    assert rig.p2.board[0].hp + rig.p2.board[1].hp == (5 + 5) - 4
    assert [c.template.id for c in rig.p1.hand] == [1, 1, 1, 1]


@synthetic_card(
    386,
    cost=4,
    attack=3,
    hp=3,
)
class Pizzapants(Monster):
    # Magic: Gain +1/+1 for each other ally Pizzapants you played this game.
    played_count: Var[int] = Var(int)

    magic = SetVar(
        var=played_count,
        value=COUNT(
            CARDS_PLAYED(player=YOU)
            & (TEMPLATE_ID == SELF.template_id)
            & (CARD_ID != SELF.id)
        ),
    ) >> SELF.buff(attack=played_count, hp=played_count)


def test_pizzapants():
    rig = TestRig.create(p1_deck=[386, 386, 1, 386], p2_deck=[1])

    rig.p1.play_monster(rig.p1.hand[0])
    assert rig.p1.board[0].attack == rig.p1.board[0].hp == 3

    rig.p1.play_monster(rig.p1.hand[0])
    assert rig.p1.board[1].attack == rig.p1.board[1].hp == 4

    rig.p1.end_turn()

    rig.p2.play_monster(rig.p2.hand[0])
    rig.p2.end_turn()

    rig.p1.play_monster(rig.p1.hand[0])
    rig.p1.play_monster(rig.p1.hand[0])
    assert rig.p1.board[3].attack == rig.p1.board[3].hp == 5


@synthetic_card(
    796,
    cost=1,
    tribes=(Tribe.GIGA_ATTACK,),
)
class GigaPunch(Spell):
    pass


@synthetic_card(
    797,
    cost=1,
    tribes=(Tribe.GIGA_ATTACK,),
)
class GigaMissiles(Spell):
    pass


@synthetic_card(
    798,
    cost=1,
    tribes=(Tribe.GIGA_ATTACK,),
)
class GigaGlass(Spell):
    pass


@synthetic_card(
    799,
    cost=1,
    tribes=(Tribe.GIGA_ATTACK,),
)
class GigaBalls(Spell):
    pass


@synthetic_card(
    721,
    cost=1,
    tribes=(Tribe.BARGAIN,),
)
class PressF1ForHelp(Spell):
    pass


@synthetic_card(
    794,
    cost=1,
    attack=1,
    hp=4,
)
class GIGAQueen(Monster):
    # Magic: Look At All Giga Attacks You Haven't Cast And Add One To Your Hand.
    magic = (
        YOU.choose(
            (
                CARD_LIBRARY
                & HAS_TRIBE(Tribe.GIGA_ATTACK)
                & ~HAS_TRIBE(Tribe.ALL)
                & ~IN_HISTORY(SPELLS_CAST(player=YOU))
            ) >> GENERATE_CARD()
        ).to(
            CHOICE_SELECTED.to_hand()
        )
    )


def test_gigaqueen():
    rig = TestRig.create(p1_deck=[794, 794, 794])

    for _ in range(2):
        rig.p1.play_monster(rig.p1.hand[0])
        choices = rig.get_choices()
        assert [c.template.id for c in choices] == [796, 797, 798, 799]

        rig.p1.choose([choices[0]])
        assert choices[0].zone is CardZone.HAND

    rig.p1.play_spell(rig.p1.hand[-1])

    rig.p1.play_monster(rig.p1.hand[0])
    choices = rig.get_choices()
    assert [c.template.id for c in choices] == [797, 798, 799]
