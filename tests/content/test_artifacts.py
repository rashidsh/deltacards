from deltacards.dsl.api import *

from ..rig import TestRig


@artifact(11)
class Preservation(Artifact):
    name = "Preservation"
    rarity = ArtifactRarity.COMMON
    initial_counter = 7

    def on_would_overdraw(self, player: 'Player', **kwargs):
        if player.id != self.controller_id:
            return None

        if self.counter <= 0:
            return None

        return SELF.update_artifact_counter(-1)


def test_preservation_overdraw_prevention():
    rig = TestRig.create(p1_artifacts=[11], p1_deck=[83, 83, 83, 1], p2_deck=[83, 83, 83, 1])

    rig.p1.play_spell(rig.p1.hand[0])
    assert len(rig.p1.hand) == 6
    assert len(rig.p1.deck) == 18

    rig.p1.play_spell(rig.p1.hand[0])
    assert len(rig.p1.hand) == 7
    assert len(rig.p1.deck) == 16

    rig.p1.play_spell(rig.p1.hand[0])
    assert len(rig.p1.hand) == 7
    assert len(rig.p1.deck) == 15

    rig.p1.end_turn()

    rig.p2.play_spell(rig.p2.hand[0])
    assert len(rig.p2.hand) == 6
    assert len(rig.p2.deck) == 18

    rig.p2.play_spell(rig.p2.hand[0])
    assert len(rig.p2.hand) == 7
    assert len(rig.p2.deck) == 15


@artifact(39)
class Reverberation(Artifact):
    name = "Reverberation"
    rarity = ArtifactRarity.LEGENDARY

    on_monster_summoned = on_event(
        MonsterSummonedResult,
        condition=EVENT.matches(
            EVENT.is_played,
            EVENT.subject.controller_id == SELF.controller_id,
            HAS_ABILITY(TURBO),
        ),
        effect=RESOLVE_ENTITY(EVENT.monster_id).trigger_ability(TURBO)
    )


def test_reverberation():
    rig = TestRig.create(p1_deck=[288], p1_artifacts=[39])
    assert [c.template.id for c in rig.p1.hand] == [288, 1, 1, 1]

    rig.p1.play_monster(rig.p1.hand[0])
    assert [c.template.id for c in rig.p1.hand] == [1, 1, 1, 1]


@artifact(52)
class SeamsSeap(Artifact):
    name = "Seam's Seap"
    rarity = ArtifactRarity.LEGENDARY

    generated_card: Var[TargetSelector] = Var(TargetSelector)
    last_counter_turn: StateVar[int | None] = StateVar(default=None)

    on_card_played = on_event(
        CardPlayedResult,
        condition=EVENT.matches(
            EVENT.player_id == SELF.controller_id,
            YOU.gold == 0,
        ),
        effect=OncePerTurn(
            last_counter_turn,
            SELF.update_artifact_counter(+1)
        )
    )

    turn_start = Check(SELF.counter >= 2).to(
        SELF.update_artifact_counter(-2)
        >> SetVar(
            var=generated_card,
            value=GENERATE_CARD("Shadow Crystal"),
        )
        >> generated_card.set_stats(cost=0)
        >> generated_card.to_hand()
    )


def test_seamsseap():
    rig = TestRig.create(p1_deck=[1, 1, 1, 1], p1_artifacts=[52], starting_gold=2)
    assert rig.p1.obj.artifacts[0].counter == 0

    rig.p1.play_monster(rig.p1.hand[0])
    assert rig.p1.gold == 1
    assert rig.p1.obj.artifacts[0].counter == 0

    rig.p1.play_monster(rig.p1.hand[0])
    assert rig.p1.gold == 0
    assert rig.p1.obj.artifacts[0].counter == 1

    rig.p1.obj.gold += 1
    rig.p1.play_monster(rig.p1.hand[0])
    assert rig.p1.gold == 0
    assert rig.p1.obj.artifacts[0].counter == 1
    assert rig.p1.obj.artifacts[0].state == {'last_counter_turn': 1}
