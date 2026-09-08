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


@artifact(80)
class TheForbiddenPath(QuestArtifact):
    name = "The Forbidden Path"
    rarity = ArtifactRarity.TOKEN

    quest_goal = 9

    generated_card: Var[Card] = Var(Card)

    def _gain_progress(self, amount: int):
        return (
            SELF.update_artifact_counter(
                LEAST(
                    amount,
                    SELF.quest_goal - SELF.counter
                )
            )
            >> Check(
                SELF.counter >= SELF.quest_goal
            ).to(
                YOU.add_artifact(
                    ARTIFACT_BY_NAME("Shattered Rose")
                )
                >> SetVar(
                    var=self.generated_card,
                    value=GENERATE_CARD("Proceed")
                )
                >> self.generated_card.set_status(LOOP, value=2)
                >> self.generated_card.to_hand()
                >> SELF.toggle_artifact(False)
            )
        )

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        killer = game.entity(res.killer_id)
        if not isinstance(killer, Monster):
            return None

        if res.killer.controller_id != self.controller_id:
            return None

        return self._gain_progress(1)

    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if not res.is_played:
            return None

        if res.card.template.name != "Snowgrave":
            return None

        return self._gain_progress(9)
