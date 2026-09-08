from deltacards.dsl.api import *


def _lose_counter_and_expire_at_zero():
    return (
        SELF.update_enchantment_counter(-1)
        >> Check(SELF.counter == 0).to(
            SELF.expire_enchantment()
        )
    )


@enchantment('blue-bones')
class BlueBones(Enchantment):
    name = "Blue Bones"

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker.slot_id != self.slot_id:
            return None

        attacker = game.entity(res.attacker_id)
        if not isinstance(attacker, Monster):
            return None

        return (
            attacker.actions.hit(5)
            >> SELF.expire_enchantment()
        )


@enchantment('x')
class XEnchantment(Enchantment):
    name = "X"

    turn_end = YOU.hit(1)

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.slot_id != self.slot_id:
            return None

        return SELF.transform_enchantment(
            ENCHANTMENT_BY_NAME("O")
        )


@enchantment('a')
class AEnchantment(Enchantment):
    name = "A"

    turn_end = YOU.hit(1)

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.slot_id != self.slot_id:
            return None

        return SELF.transform_enchantment(
            ENCHANTMENT_BY_NAME("X")
        )


@enchantment('o')
class OEnchantment(Enchantment):
    name = "O"

    turn_end = Check(
        COUNT(
            ALLY_SLOTS
            & SLOT_HAS_ENCHANTMENT("O")
        ) == 4
    ).to(
        ALLY_ENCHANTMENTS.expire_enchantment()
    )

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.slot_id != self.slot_id:
            return None

        return SELF.transform_enchantment(
            ENCHANTMENT_BY_NAME("A")
        )


@enchantment('green-tile')
class GreenTile(Enchantment):
    name = "Green Tile"

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.slot_id != self.slot_id:
            return None

        return (
            GENERATE_CARD("Papyrus Statue", controller=OPPONENT).summon(controller=OPPONENT)
            >> SELF.expire_enchantment()
        )


@enchantment('yellow-tile')
class YellowTile(Enchantment):
    name = "Yellow Tile"

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.slot_id != self.slot_id:
            return None

        return (
            (
                ALLY_MONSTERS
                & (ID != res.monster_id)
            ).hit(3)
            >> SELF.expire_enchantment()
        )


@enchantment('purple-tile')
class PurpleTile(Enchantment):
    name = "Purple Tile"

    # TODO unsure how it's implemented
    pass


@enchantment('orange-tile')
class OrangeTile(Enchantment):
    name = "Orange Tile"

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.slot_id != self.slot_id:
            return None

        return (
            (OPPONENT.draw_next() * 3)
            >> SELF.expire_enchantment()
        )


@enchantment('the-flame')
class TheFlame(Enchantment):
    name = "The Flame"

    turn_end = YOU.hit(2)

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.slot_id != self.slot_id:
            return None

        return (
            RESOLVE_ENTITY(res.monster_id).hit(2)
            >> SELF.expire_enchantment()
        )


@enchantment('scattering-dust')
class ScatteringDust(Enchantment):
    name = "Scattering Dust"
    initial_counter = 2

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.slot_id != self.slot_id:
            return None

        if res.monster.template.name == "Pile of Dust":
            return None

        if game.turn_player.id == self.controller_id:
            return None

        return (
            GENERATE_CARD("Pile of Dust").summon(pos=res.monster.pos)
            >> _lose_counter_and_expire_at_zero()
        )


@enchantment('incinerator')
class Incinerator(Enchantment):
    name = "Incinerator"
    initial_counter = 5

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.slot_id != self.slot_id:
            return None

        other_ally_monsters = (
            ALLY_MONSTERS
            & (ID != res.monster_id)
        )

        return Check(
            EXISTS(other_ally_monsters)
        ).to(
            RESOLVE_ENTITY(res.monster_id).kill().to(
                (
                    other_ally_monsters
                    >> RANDOM(1)
                ).buff(attack=+1, hp=+1)
                >> _lose_counter_and_expire_at_zero()
            )
        )


@enchantment('the-cure')
class TheCure(Enchantment):
    name = "The Cure"

    turn_end = Check(
        EXISTS(THIS_SLOT_MONSTER)
    ).to(
        THIS_SLOT_MONSTER.remove_negative_effects()
        >> THIS_SLOT_MONSTER.add_keyword(KR)
    )


@enchantment('soil')
class Soil(Enchantment):
    name = "Soil"

    turn_end = Check(
        ~EXISTS(THIS_SLOT_MONSTER)
    ).to(
        GENERATE_CARD("Green Clover").summon(pos=SLOT_OF(SELF).pos)
    )
