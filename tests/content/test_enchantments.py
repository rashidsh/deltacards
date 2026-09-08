from deltacards.dsl.api import *

from ..card_templates import synthetic_card
from ..rig import TestRig


def _lose_counter_and_expire_at_zero():
    return (
        SELF.update_enchantment_counter(-1)
        >> Check(SELF.counter == 0).to(
            SELF.expire_enchantment()
        )
    )


def _attached_enchantment(
    rig: TestRig,
    slot: BoardSlot,
) -> Enchantment | None:
    if slot.enchantment_id is None:
        return None

    entity = rig.game.entity(slot.enchantment_id)
    assert isinstance(entity, Enchantment)
    assert entity.active
    assert entity.slot_id == slot.id

    return entity


@synthetic_card(
    490,
    name="Pile of Dust",
    cost=1,
    attack=1,
    hp=4,
)
class PileOfDust(Monster):
    pass


@enchantment('scattering-dust')
class ScatteringDust(Enchantment):
    name = "Scattering Dust"
    initial_counter = 2

    on_monster_killed = on_event(
        MonsterKilledResult,
        condition=EVENT.matches(
            EVENT.subject.slot_id == SELF.slot_id,
            EVENT.subject.template_name != "Pile of Dust",
            TURN_PLAYER.id != SELF.controller_id,
        ),
        effect=(
            GENERATE_CARD("Pile of Dust").summon(pos=EVENT.subject.pos)
            >> _lose_counter_and_expire_at_zero()
        )
    )


@synthetic_card(
    183,
    cost=1,
)
class Aftermath(Spell):
    magic = (
        (ENEMY_SLOTS & OCCUPIED_SLOT)
        >> RANDOM(2)
    ).enchant(
        ENCHANTMENT_BY_NAME("Scattering Dust")
    )


def test_aftermath_and_scattering_dust():
    rig = TestRig.create(
        p1_deck=[183, 129, 129],
        p2_deck=[1, 1, 1],
    )

    rig.p1.end_turn()

    for _ in range(3):
        rig.p2.play_monster(rig.p2.hand[0])

    rig.p2.end_turn()

    aftermath = rig.p1.hand[0]
    rig.p1.play_spell(aftermath)

    enchanted_slots = [
        slot for slot in rig.p2.obj.board_slots
        if slot.enchantment_id is not None
    ]

    assert len(enchanted_slots) == 2
    assert all(
        slot.monster_id is not None
        for slot in enchanted_slots
    )

    for slot in enchanted_slots:
        enchantment = _attached_enchantment(rig, slot)
        assert enchantment is not None
        assert enchantment.name == "Scattering Dust"
        assert enchantment.counter == 2

    triggered_slot = enchanted_slots[0]
    original_monster = rig.game.entity(triggered_slot.monster_id)

    # Play Knife on Dummy
    rig.p1.play_spell(rig.p1.hand[0], target=original_monster)

    assert triggered_slot.monster_id is not None

    pile_of_dust = rig.game.entity(triggered_slot.monster_id)
    assert isinstance(pile_of_dust, Monster)
    assert pile_of_dust.template.name == "Pile of Dust"

    scattering_dust = _attached_enchantment(rig, triggered_slot)
    assert scattering_dust is not None
    assert scattering_dust.name == "Scattering Dust"
    assert scattering_dust.counter == 1

    # Play Knife on Pile of Dust
    rig.p1.play_spell(rig.p1.hand[0], target=pile_of_dust)

    assert triggered_slot.monster_id is None
    assert triggered_slot.enchantment_id == scattering_dust.id
    assert scattering_dust.active
    assert scattering_dust.counter == 1


@enchantment('the-cure')
class TheCure(Enchantment):
    name = "The Cure"

    turn_end = Check(
        EXISTS(THIS_SLOT_MONSTER)
    ).to(
        THIS_SLOT_MONSTER.remove_negative_effects()
        >> THIS_SLOT_MONSTER.add_keyword(KR)
    )


@synthetic_card(
    950,
    cost=1,
    attack=1,
    hp=4,
)
class PlagueDoctor(Monster):
    targets = ALLY_SLOTS

    magic = TARGET.enchant(
        ENCHANTMENT_BY_NAME("The Cure")
    )


def test_plague_doctor_and_the_cure():
    rig = TestRig.create(p1_deck=[490, 950])

    ally = rig.p1.hand[0]
    plague_doctor = rig.p1.hand[1]

    rig.p1.play_monster(ally, slot=0)

    ally.buff(cost=+2, attack=-1, hp=-2)
    ally.add_keyword(CardKeyword.DISARMED)
    ally.set_status(CardStatusId.PARALYZED, 2)

    target_slot = rig.p1.obj.board_slots[0]

    rig.p1.play_monster(
        plague_doctor,
        slot=1,
        target=target_slot,
    )

    cure = _attached_enchantment(rig, target_slot)
    assert cure is not None
    assert cure.name == "The Cure"

    assert ally.cost > ally.base.cost
    assert ally.attack < ally.base.attack
    assert ally.max_hp < ally.base.hp
    assert ally.has_keyword(CardKeyword.DISARMED)
    assert ally.get_status(CardStatusId.PARALYZED) == 2

    rig.p1.end_turn()

    assert ally.cost == ally.base.cost
    assert ally.attack == ally.base.attack
    assert ally.max_hp == ally.base.hp

    assert not ally.has_keyword(CardKeyword.DISARMED)
    assert ally.get_status(CardStatusId.PARALYZED) == 0
    assert ally.has_keyword(CardKeyword.KR)

    assert target_slot.enchantment_id == cure.id
    assert cure.active


@enchantment('the-flame')
class TheFlame(Enchantment):
    name = "The Flame"

    turn_end = YOU.hit(2)

    on_monster_summoned = on_event(
        MonsterSummonedResult,
        condition=EVENT.matches(
            EVENT.is_played,
            EVENT.subject.slot_id == SELF.slot_id,
        ),
        effect=(
            RESOLVE_ENTITY(EVENT.monster_id).hit(2)
            >> SELF.expire_enchantment()
        )
    )


@synthetic_card(
    951,
    cost=1,
    attack=1,
    hp=4,
)
class FireFountain(Monster):
    dust = DEATH_SLOT.enchant(
        ENCHANTMENT_BY_NAME("The Flame")
    )


def test_fire_fountain_and_the_flame():
    rig = TestRig.create(p1_deck=[951, 129])

    fire_fountain = rig.p1.hand[0]
    knife = rig.p1.hand[1]

    target_slot = rig.p1.obj.board_slots[2]

    rig.p1.play_monster(fire_fountain, slot=2)
    assert target_slot.monster_id == fire_fountain.id

    rig.p1.play_spell(knife, target=fire_fountain)
    assert fire_fountain.zone is CardZone.DUSTPILE
    assert target_slot.monster_id is None

    flame = _attached_enchantment(rig, target_slot)
    assert flame is not None
    assert flame.name == "The Flame"

    hp_before_turn_end = rig.p1.hp
    rig.p1.end_turn()

    assert rig.p1.hp == hp_before_turn_end - 2
    assert target_slot.enchantment_id == flame.id
    assert flame.active
