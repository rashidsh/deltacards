from deltacards.dsl.api import *
from deltacards.model.artifacts import (
    ArtifactRarity,
    QuestArtifact,
    artifact,
)

from ..card_templates import synthetic_card
from ..rig import TestRig


@artifact(77)
class PowerOfFriendship(QuestArtifact):
    name = "Power of Friendship"
    rarity = ArtifactRarity.TOKEN

    quest_goal = 6

    reward_cards: Var[TargetSelector] = Var(TargetSelector)

    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        played_card = game.entity(res.card_id)
        if not isinstance(played_card, Monster):
            return None

        if not res.has_need_condition:
            return None

        if not res.need_fulfilled:
            return None

        return (
            SELF.update_artifact_counter(+1)
            >> Check(SELF.counter >= self.quest_goal).to(
                SetVar(
                    var=PowerOfFriendship.reward_cards,
                    value=(
                        (
                            CARDS_PLAYED(player=YOU)
                            & IS_MONSTER
                            & HAS_NEED_CONDITION
                            & NEED_FULFILLED
                        )
                        >> AS_TEMPLATES()
                        >> GENERATE_CARD()
                    )
                )
                >> PowerOfFriendship.reward_cards.add_keyword(FLOWERY_POWER)
                >> AddToHandOrDeck(PowerOfFriendship.reward_cards)
                >> SELF.toggle_artifact(False)
            )
        )


@synthetic_card(
    986,
    cost=1,
    attack=1,
    hp=4,
)
class Flowery(Monster):
    game_start = YOU.add_artifact(
        ARTIFACT_BY_NAME("Power of Friendship")
    )


@synthetic_card(
    10008,
    name="Friendship Sprout",
    cost=0,
    attack=1,
    hp=1,
)
class FriendshipSprout(Monster):
    # This condition becomes false after the Quest is disabled. Reward copies
    # can still fulfill it because they receive Flowery Power.
    need = YOU.artifact("Power of Friendship").active

    magic = (
        SELF.kill()
        >> Check(
            COUNT(
                CARDS_PLAYED(player=YOU)
                & (TEMPLATE_NAME == "Friendship Sprout")
            ) == 0
        ).to(
            YOU.draw_next()
        )
        >> GENERATE_CARD("Friendship Sprout").to_hand()
    )


@synthetic_card(
    10009,
    name="Unfulfilled Friendship",
    cost=0,
    attack=1,
    hp=1,
)
class UnfulfilledFriendship(Monster):
    need = COUNT(ALL_MONSTERS) < 0

    magic = NO_EFFECT


def _played_result(rig: TestRig, card: Card) -> CardPlayedResult:
    return next(
        res
        for res in reversed(rig.game.log)
        if (
            isinstance(res, CardPlayedResult)
            and res.card_id == card.id
        )
    )


def test_power_of_friendship_quest_reward_and_flowery_power():
    rig = TestRig.create(p1_deck=[986, 10008, 1, 1, 10009])

    assert len(rig.p1.obj.artifacts) == 1

    quest = rig.p1.obj.artifacts[0]
    assert isinstance(quest, QuestArtifact)
    assert quest.name == "Power of Friendship"
    assert quest.is_quest
    assert quest.quest_goal == 6
    assert quest.counter == 0
    assert quest.active

    flowery = next(
        card
        for card in rig.p1.hand
        if card.template.name == "Flowery"
    )
    rig.p1.play_monster(flowery)

    for expected_counter in range(1, 7):
        sprout = next(
            card
            for card in rig.p1.hand
            if card.template.name == "Friendship Sprout"
        )

        rig.p1.play_monster(sprout)

        result = _played_result(rig, sprout)
        assert result.has_need_condition
        assert result.need_fulfilled
        assert quest.counter == expected_counter

        if expected_counter == 1:
            unfulfilled = next(
                card
                for card in rig.p1.hand
                if card.template.name == "Unfulfilled Friendship"
            )

            rig.p1.play_monster(unfulfilled)

            result = _played_result(rig, unfulfilled)
            assert result.has_need_condition
            assert not result.need_fulfilled
            assert quest.counter == 1

    assert quest.counter == quest.quest_goal
    assert not quest.active

    sprout_cards = [
        card
        for card in [*rig.p1.hand, *rig.p1.deck]
        if card.template.name == "Friendship Sprout"
    ]
    reward_cards = [
        card
        for card in sprout_cards
        if card.has_keyword(FLOWERY_POWER)
    ]
    ordinary_cards = [
        card
        for card in sprout_cards
        if not card.has_keyword(FLOWERY_POWER)
    ]

    assert len(reward_cards) == 6
    assert len(ordinary_cards) == 1

    assert all(
        card.zone in (CardZone.HAND, CardZone.DECK)
        for card in reward_cards
    )
    assert all(
        card.has_keyword(FLOWERY_POWER)
        for card in reward_cards
    )

    reward = next(
        card
        for card in reward_cards
        if card.zone is CardZone.HAND
    )

    # The ordinary Need condition is now false because the Quest is inactive.
    reward.remove_keyword(FLOWERY_POWER)
    assert not rig.game.card_need_fulfilled(reward)

    reward.add_keyword(FLOWERY_POWER)
    assert rig.game.card_need_fulfilled(reward)

    rig.p1.play_monster(reward)

    result = _played_result(rig, reward)
    assert result.has_need_condition
    assert result.need_fulfilled

    # Disabled Quest Artifacts no longer receive events.
    assert quest.counter == quest.quest_goal
    assert not quest.active
