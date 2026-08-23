from deltacards.dsl.api import *


@artifact(76)
class DokiMeter(QuestArtifact):
    name = "Doki-Meter!"
    rarity = ArtifactRarity.TOKEN

    quest_goal = 15

    turn_start = Check(
        COUNT(HAND & (TEMPLATE_NAME == "Mew Mew Magic")) == 0
    ).to(
        GENERATE_CARD("Mew Mew Magic").to_hand()
    )


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
