from deltacards.dsl.api import *
from deltacards.model.artifacts import Artifact, ArtifactRarity, artifact


@artifact(7)
class Experience(Artifact):
    name = "Experience"
    rarity = ArtifactRarity.COMMON

    # No effect here


@artifact(8)
class Reinforcement(Artifact):
    name = "Reinforcement"
    rarity = ArtifactRarity.COMMON

    turn_start = Check(YOU.turn % 10 == 0).to(
        GENERATE_CARD("Draft").to_hand() * 2
    )

    turn_end = Check(YOU.turn % 10 == 0).to(
        (HAND & IS_MONSTER).buff(attack=+1, hp=+1)
    )


@artifact(9)
class Ambition(Artifact):
    name = "Ambition"
    rarity = ArtifactRarity.COMMON

    turn_end = Check(
        (YOU.turn % 3 == 0)
        & ~EXISTS((HAND | DECK) & (TEMPLATE_NAME == "Dream"))
    ).to(
        GENERATE_CARD("Dream").to_deck(pos='top')
    )


@artifact(10)
class Prosperity(Artifact):
    name = "Prosperity"
    rarity = ArtifactRarity.COMMON

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.is_generated:
            return None

        if res.monster.base.cost < 4:
            return None

        return YOU.heal(1)


@artifact(11)
class Preservation(Artifact):
    name = "Preservation"
    rarity = ArtifactRarity.COMMON
    initial_counter = 7

    def on_would_overdraw(self, player, **kwargs):
        if player.id != self.controller_id:
            return None

        if self.counter <= 0:
            return None

        return SELF.update_artifact_counter(-1)


@artifact(14)
class Copycat(Artifact):
    name = "Copycat"
    rarity = ArtifactRarity.COMMON

    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    game_start = (
        OPPONENT_HAND[:3].reveal()
        >> SetVar(
            var=copied_cards,
            value=OPPONENT_HAND[:3] >> COPY(controller=YOU),
        )
        >> copied_cards.buff(cost=-1)
        >> copied_cards.to_deck()
    )


@artifact(17)
class SpikeBand(Artifact):
    name = "Spike Band"
    rarity = ArtifactRarity.COMMON

    def _spike_band_effect(self):
        yield SELF.toggle_artifact(False)

        hit_result = yield ENEMY_MONSTERS.hit(3)

        excess_damage = sum(res.excess_damage for res in hit_result.results if isinstance(res, EntityDamagedResult))
        if excess_damage > 0:
            yield YOU.heal(excess_damage)

    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.controller_id:
            return None

        if game.players[self.controller_id].hp > 15:
            return None

        return self._spike_band_effect()


@artifact(19)
class Spy(Artifact):
    name = "Spy"
    rarity = ArtifactRarity.COMMON

    turn_start = Check(YOU.turn % 3 == 0).to(
        (OPPONENT_HAND & IS_SPELL).first().buff(cost=+1) >> OPPONENT_HAND.reveal()
    )


@artifact(20)
class Hourglass(Artifact):
    name = "Hourglass"
    rarity = ArtifactRarity.COMMON
    initial_counter = 5

    @on_event(GoldSpentResult)
    def on_gold_spent(self, res: GoldSpentResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if not res.is_generated:
            return None

        yield SELF.update_artifact_counter(-1)

        if self.counter <= 0:
            yield (
                GENERATE_CARD("Time Warp").to_hand()
                >> SELF.update_artifact_counter(+5)
            )

        return None


@artifact(26)
class Parachutism(Artifact):
    name = "Parachutism"
    rarity = ArtifactRarity.COMMON

    turn_start = Check(
        (YOU.turn >= 4) & (((YOU.turn - 4) % 3) == 0)
    ).to(
        GENERATE_CARD("Mettabot").summon()
    )


@artifact(27)
class Doom(Artifact):
    name = "Doom"
    rarity = ArtifactRarity.COMMON

    turn_start = Check(YOU.turn % 12 == 0).to(
        ALL_MONSTERS.silence()
        >> ALL_MONSTERS.kill()
    )


@artifact(29)
class Wiggle(Artifact):
    name = "Wiggle"
    rarity = ArtifactRarity.COMMON

    game_start = GENERATE_CARD("Moldsmal").to_hand()

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.is_generated:
            return None

        if not res.monster.has_tribe(Tribe.MOLD):
            return None

        return game.entity(res.monster.id).actions.add_keyword(HASTE)


@artifact(30)
class AbsorbAx(Artifact):
    name = "AbsorbAx"
    rarity = ArtifactRarity.LEGENDARY

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id == self.controller_id:
            return None

        if res.monster.is_generated:
            return None

        return YOU.buff(hp=+1)


@artifact(31)
class Noodles(Artifact):
    name = "Noodles"
    rarity = ArtifactRarity.COMMON

    game_start = GENERATE_CARD("Instant Noodles").to_hand()


@artifact(36)
class EvilPlan(Artifact):
    name = "Evil Plan"
    rarity = ArtifactRarity.COMMON

    X: Var[Card] = Var(Card)
    generated_card: Var[Card] = Var(Card)

    game_start = Check((BOARD | HAND | DECK) & (TEMPLATE_NAME == "Ultimathrash")).to(
        SELF.transform_artifact(ARTIFACT_BY_NAME("Ultimate Fusion"))
    )

    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if len(game.player(self.controller_id).hand) > 0:
            return None

        return ForEach(
            CARD_LIBRARY & HAS_TRIBE(Tribe.THRASHING_PART) & ~HAS_TRIBE(Tribe.ALL),
            var=self.X,
            effect=(
                SetVar(
                    var=self.generated_card,
                    value=self.X >> GENERATE_CARD(),
                )
                >> self.generated_card.buff(attack=+1)
                >> self.generated_card.to_hand()
            )
        ) >> SELF.toggle_artifact(False)


@artifact(40)
class GoodFood(Artifact):
    name = "Good Food"
    rarity = ArtifactRarity.COMMON

    shock = YOU.heal(1)


@artifact(53)
class Glamburger(Artifact):
    name = "Glamburger"
    rarity = ArtifactRarity.COMMON

    turn_start = Check(
        (YOU.turn == 4)
        | (YOU.turn == 7)
        | (YOU.turn == 10)
    ).to(
        YOU.earn_gold(1)
    )


@artifact(54)
class GenerousGifts(Artifact):
    name = "Generous Gifts"
    rarity = ArtifactRarity.COMMON

    gift: Var[Card] = Var(Card)

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.cost < 4:
            return None

        return (
            SELF.update_artifact_counter(+1)
            >> Check((SELF.counter % 5) == 0).to(
                Check(EMPTY_SLOTS(BOARD) > 0).to(
                    SetVar(var=GenerousGifts.gift, value=GENERATE_CARD("Gift"))
                    >> GenerousGifts.gift.summon().to(
                        GenerousGifts.gift.buff(
                            attack=SELF.counter // 5,
                            hp=SELF.counter // 5,
                        )
                    )
                )
            )
        )


@artifact(66)
class Gachapon(Artifact):
    name = "Gachapon"
    rarity = ArtifactRarity.COMMON

    turn_start = Check(YOU.turn % 3 == 0).to(
        GENERATE_CARD("Gacha Ball").to_hand()
    )


@artifact(73)
class ElectroGuitar(Artifact):
    name = "Electro Guitar"
    rarity = ArtifactRarity.COMMON

    turn_start = Check(SELF.counter >= 4).to(
        SELF.update_artifact_counter(-4)
        >> GENERATE_CARD("Rock Chord").to_hand()
    )

    turn_end = Check(EMPTY_SLOTS(BOARD) == 0).to(
        SELF.update_artifact_counter(+1)
    )


@artifact(74)
class PixelCamera(Artifact):
    name = "Pixel Camera"
    rarity = ArtifactRarity.COMMON

    copies: Var[TargetSelector] = Var(TargetSelector)

    turn_end = Check(EMPTY_SLOTS(BOARD) == 0).to(
        SetVar(
            var=copies,
            value=(ALLY_MONSTERS & NON_DT) >> COPY(),
        )
        >> copies.buff(cost=-1)
        >> copies.move_to(CardZone.DECK)
        >> SELF.toggle_artifact(False)
    )
