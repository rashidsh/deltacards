from deltacards.dsl.api import *

from ..card_templates import synthetic_card
from ..rig import TestRig


@synthetic_card(
    923,
    cost=1,
    attack=2,
    hp=6,
)
class PixelKris(Monster):
    # Has +1 ATK for each missing HP.
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="+1 ATK for each missing HP",
            applies=lambda q: q.monster is self,
            apply=lambda attack, q: attack + self.hp_missing,
        )


def test_card_pixelkris():
    rig = TestRig.create(p1_deck=[923], p2_deck=[923])

    attacker = rig.p1.hand[0]
    rig.p1.play_monster(attacker, slot=0)
    rig.p1.end_turn()

    defender = rig.p2.hand[0]
    rig.p2.play_monster(defender, slot=0)
    rig.p2.end_turn()

    # Base ATK of Pixel Kris is 2
    rig.p1.attack(attacker, defender)

    assert attacker.zone is CardZone.BOARD
    assert attacker.attack == attacker.base.attack + 2
    assert attacker.hp == attacker.base.hp - 2

    assert defender.zone is CardZone.BOARD
    assert defender.attack == defender.base.attack + 2
    assert defender.hp == defender.base.hp - 2


@synthetic_card(
    632,
    cost=1,
    attack=2,
    hp=5,
)
class Trashy(Monster):
    # This has +2 ATK on the enemy turn and takes no DMG while attacking.
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="+2 ATK on the enemy turn",
            applies=lambda q: q.monster is self and game.turn_player.id != self.controller_id,
            apply=lambda attack, q: attack + 2,
        )

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.PREVENT,
            source=self,
            description="Takes no DMG while attacking",
            applies=lambda q: (
                q.target is self
                and q.kind is DamageKind.COMBAT
                and q.combat_attacker is self
            ),
            apply=lambda damage, q: 0,
        )


def test_card_trashy():
    rig = TestRig.create(p1_deck=[632], p2_deck=[632])

    attacker = rig.p1.hand[0]
    rig.p1.play_monster(attacker, slot=0)
    rig.p1.end_turn()

    defender = rig.p2.hand[0]
    rig.p2.play_monster(defender, slot=0)
    rig.p2.end_turn()

    # Base ATK of Trashy is 2
    rig.p1.attack(attacker, defender)

    assert attacker.zone is CardZone.BOARD
    assert attacker.attack == attacker.base.attack
    assert attacker.hp == attacker.base.hp

    assert defender.zone is CardZone.BOARD
    assert defender.attack == defender.base.attack + 2
    assert defender.hp == defender.base.hp - 2


@synthetic_card(
    559,
    cost=1,
    attack=1,
    hp=4,
)
class LaggyTV(Monster):
    # Monsters in your hand have +1 COST. Whenever you play a monster, give it +1/+2.
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        def applies(q: CostQuery) -> bool:
            return (
                q.card.zone is CardZone.HAND
                and isinstance(q.card, Monster)
                and q.card.controller_id == self.controller_id
            )

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="Monsters in your hand have +1 COST",
            applies=applies,
            apply=lambda cost, q: cost + 1,
        )

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        monster = game.entity(res.monster_id)
        if monster.controller_id != self.controller_id:
            return None

        return monster.actions.buff(attack=+1, hp=+2)


def test_card_laggytv():
    rig = TestRig.create(p1_deck=[559, 1, 79, 1], p2_deck=[1])

    laggy_tv = rig.p1.hand[0]
    dummy = rig.p1.hand[1]
    penetration = rig.p1.hand[2]
    dummy_2 = rig.p1.hand[3]
    opponent_dummy = rig.p2.hand[0]

    rig.p1.play_monster(laggy_tv)

    assert laggy_tv.attack == laggy_tv.base.attack
    assert laggy_tv.hp == laggy_tv.base.hp
    assert dummy.cost == dummy.base.cost + 1
    assert dummy_2.cost == dummy_2.base.cost + 1
    assert penetration.cost == penetration.base.cost
    assert opponent_dummy.cost == opponent_dummy.base.cost

    rig.p1.play_monster(dummy)

    assert dummy.attack == dummy.base.attack + 1
    assert dummy.hp == dummy.base.hp + 2
    assert dummy.cost == dummy.base.cost

    rig.p1.play_spell(penetration, target=laggy_tv)

    # Cost modification should no longer apply
    assert dummy_2.cost == dummy_2.base.cost


@synthetic_card(
    145,
    cost=1,
    attack=1,
    hp=4,
)
class DiamondBoy1(Monster):
    # All other non-Armor ally monsters take 1 less DMG (can't stack).
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        def applies(q: DamageQuery) -> bool:
            return (
                q.target is not self
                and isinstance(q.target, Monster)
                and q.target.controller_id == self.controller_id
                and not q.target.has_keyword(CardKeyword.ARMOR)
            )

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="Other non-Armor ally monsters take 1 less DMG (can't stack)",
            applies=applies,
            apply=lambda damage, q: damage - 1,
            unique=True,
            key="non_armor_allies:-1_damage",
        )


def test_card_diamondboy1():
    rig = TestRig.create(p1_deck=[145, 145, 1, 1], p2_deck=[578, 578])

    monster_1 = rig.p1.hand[0]
    monster_2 = rig.p1.hand[1]
    dummy = rig.p1.hand[2]
    dummy_with_armor = rig.p1.hand[3]
    spell_1 = rig.p2.hand[0]
    spell_2 = rig.p2.hand[1]

    rig.p1.play_monster(monster_1)
    rig.p1.play_monster(monster_2)
    rig.p1.play_monster(dummy)
    rig.p1.play_monster(dummy_with_armor)
    dummy_with_armor.add_keyword(CardKeyword.ARMOR)

    rig.p1.end_turn()

    rig.p2.play_spell(spell_1, target=dummy)
    assert dummy.hp == dummy.base.hp - 2

    rig.p2.play_spell(spell_2, target=dummy_with_armor)
    assert dummy_with_armor.hp == dummy_with_armor.base.hp - 2
