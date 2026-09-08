from deltacards.dsl.api import *


@artifact(1)
class Health(Artifact):
    name = "Health"
    rarity = ArtifactRarity.BASE

    game_start = YOU.buff(hp=+7)


@artifact(2)
class Draw(Artifact):
    name = "Draw"
    rarity = ArtifactRarity.BASE

    game_start = YOU.draw_next()

    turn_start = Check(
        (YOU.turn % 5 == 0) & (COUNT(HAND) < MAX_HAND_SIZE)
    ).to(
        YOU.draw_next()
    )


@artifact(3)
class Swarm(Artifact):
    name = "Swarm"
    rarity = ArtifactRarity.BASE

    turn_start = Check(YOU.turn == 3).to(
        GENERATE_CARD("Spider").to_hand() * 2
    )


@artifact(4)
class Power(Artifact):
    name = "Power"
    rarity = ArtifactRarity.BASE

    turn_start = Check(
        (YOU.turn >= 4) & (((YOU.turn - 4) % 3) == 0)
    ).to(
        SELF.update_artifact_counter(+1)
    )

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.controller_id != self.controller_id:
            return None

        if self.counter <= 0:
            return None

        return SELF.update_artifact_counter(-1) >> game.entity(res.monster.id).actions.buff(attack=+1, hp=+1)


@artifact(5)
class Ribbit(Artifact):
    name = "Ribbit"
    rarity = ArtifactRarity.BASE

    game_start = (
        GENERATE_CARD("Tiny Froggit").to_hand()
        >> GENERATE_CARD("Froggit").to_deck()
        >> GENERATE_CARD("Final Froggit").to_deck()
    )


@artifact(6)
class ChainMail(Artifact):
    name = "ChainMail"
    rarity = ArtifactRarity.BASE

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_keyword(CardKeyword.TAUNT):
            return None

        return GENERATE_CARD("Shield").to_deck(pos='top')
