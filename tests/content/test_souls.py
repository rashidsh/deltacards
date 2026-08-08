from deltacards.dsl.api import *
from deltacards.model.souls import Soul, soul

from ..rig import TestRig


@soul('DETERMINATION')
class Determination(Soul):
    def __init__(self, id: int, controller_id: PlayerId):
        super().__init__(id, controller_id)

        self.extra_life = True

    def game_start(self, ctx):
        controller = self._get_controller(ctx)
        controller.next_lost_soul = 0
        return YOU.add_artifact(ARTIFACT_BY_NAME("Save"))

    def on_would_die(self, entity: Entity, **kwargs):
        if entity.id == self.controller_id and self.extra_life:
            self.extra_life = False
            return entity.actions.set_hp(5)

        return None


def test_soul_determination_death_prevention():
    rig = TestRig.create(soul_id='DETERMINATION', p1_deck=[1, 129, 1, 129])
    rig.p1.obj.hp = 1

    dummy = rig.p1.hand[0]
    knife = rig.p1.hand[1]
    dummy_2 = rig.p1.hand[2]
    knife_2 = rig.p1.hand[3]

    rig.p1.play_monster(dummy)
    rig.p1.play_spell(knife, target=dummy)

    assert rig.p1.obj.hp == 5

    # Check that death is prevented only once
    rig.p1.obj.hp = 1
    rig.p1.play_monster(dummy_2)
    rig.p1.play_spell(knife_2, target=dummy_2)

    assert rig.p1.obj.hp == 0
    assert rig.game.game_over == True
    assert rig.game.dead_players == {rig.p1.id}
