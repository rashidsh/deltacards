from deltacards.dsl.api import *

from ..card_templates import synthetic_card
from ..rig import TestRig


@synthetic_card(
    17,
    cost=9,
    attack=5,
    hp=9,
)
class KnightKnight(Monster):
    # After this attacks and survives, heal this by the amount of DMG dealt.
    on_attack_resolved = on_event(
        AttackResolvedResult,
        condition=EVENT.matches(
            EVENT.attacker_id == SELF.id,
            ~EVENT.attacker_dead,
        ),
        effect=SELF.heal(EVENT.damage_to_defender)
    )


def test_card_knightknight():
    rig = TestRig.create(p1_deck=[17], p2_deck=[1, 616])

    attacker = rig.p1.hand[0]
    rig.p1.play_monster(attacker, slot=0)
    rig.p1.end_turn()

    defender = rig.p2.hand[0]
    big_monster = rig.p2.hand[1]
    rig.p2.play_monster(defender, slot=0)
    rig.p2.play_monster(big_monster, slot=1)
    rig.p2.end_turn()

    rig.p1.attack(attacker, defender)
    assert attacker.zone is CardZone.BOARD
    assert attacker.hp == attacker.base.hp

    rig.p1.end_turn()
    rig.p2.end_turn()

    rig.p1.attack(attacker, big_monster)
    assert attacker.zone is CardZone.DUSTPILE


@synthetic_card(
    60,
    cost=11,
    attack=6,
    hp=9,
    keywords=CardKeyword.CHARGE,
)
class Papyrus(Monster):
    # Charge. After this attacks and kills a monster, this can attack another monster.
    # Magic: Program (2): Gain Armor.
    magic = Program(2).to(
        SELF.add_keyword(ARMOR)
    )

    on_attack_resolved = on_event(
        AttackResolvedResult,
        condition=EVENT.matches(
            EVENT.attacker_id == SELF.id,
            ~EVENT.attacker_dead,
            EVENT.defender_dead,
        ),
        effect=SELF.refresh_attacks()
    )


def test_papyrus():
    rig = TestRig.create(p1_deck=[60, 60], p2_deck=[1, 1], starting_gold=25)

    monster_with_armor = rig.p1.hand[0]
    monster_without_armor = rig.p1.hand[1]

    rig.p1.play_monster(monster_with_armor)
    assert monster_with_armor.has_keyword(CardKeyword.ARMOR)
    assert rig.p1.gold == 25 - (11 + 2)

    rig.p1.play_monster(monster_without_armor)
    assert not monster_without_armor.has_keyword(CardKeyword.ARMOR)
    assert rig.p1.gold == 25 - (11 + 2) - 11

    rig.p1.end_turn()

    defender_1 = rig.p2.hand[0]
    defender_2 = rig.p2.hand[1]
    rig.p2.play_monster(defender_1)
    rig.p2.play_monster(defender_2)
    rig.p2.end_turn()

    # Should be able to attack both monsters in a row
    rig.p1.attack(monster_without_armor, defender_1)
    rig.p1.attack(monster_without_armor, defender_2)
