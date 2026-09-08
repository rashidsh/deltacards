from deltacards.dsl.api import *


@artifact(12)
class Science(Artifact):
    name = "Science"
    rarity = ArtifactRarity.LEGENDARY

    generated_card: Var[Card] = Var(Card)

    game_start = (
        SetVar(var=generated_card, value=GENERATE_CARD("Gaster Blaster"))
        >> generated_card.set_stats(cost=3)
        >> generated_card.to_hand()
    )

    turn_start = Check(SELF.counter >= 8).to(
        SELF.update_artifact_counter(-8)
        >> SetVar(var=generated_card, value=GENERATE_CARD("Gaster Blaster"))
        >> generated_card.set_stats(cost=2)
        >> generated_card.to_hand()
    )

    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.template.rarity is not CardRarity.TOKEN:
            return None

        if res.card.creator_base_identity == self.base_identity:
            return None

        return SELF.update_artifact_counter(res.card.cost)


@artifact(15)
class Mines(Artifact):
    name = "Mines"
    rarity = ArtifactRarity.LEGENDARY

    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if res.card.controller_id != self.controller_id:
            return None

        if not res.is_played:
            return None

        return Check(
            COUNT(SPELLS_CAST(player=YOU) & (TEMPLATE_ID == res.card.template.id)) == 1
        ).to(
            GENERATE_CARD("Mine", controller=OPPONENT).to_deck()
        )


@artifact(16)
class ArcaneScepter(Artifact):
    name = "Arcane Scepter"
    rarity = ArtifactRarity.LEGENDARY

    turn_start = GENERATE_CARD("Arcane Codes").to_hand()


@artifact(18)
class PowerBand(Artifact):
    name = "Power Band"
    rarity = ArtifactRarity.LEGENDARY

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        killer = game.entity(res.killer_id)
        if not isinstance(killer, Monster):
            return None

        if killer.controller_id != self.controller_id:
            return None

        return killer.actions.buff(attack=+1)


@artifact(28)
class Collection(Artifact):
    name = "Collection"
    rarity = ArtifactRarity.LEGENDARY

    generated_card: Var[Card] = Var(Card)

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.template.name == "Thrashing Machine":
            return None

        for tribe in res.monster.template.tribes:
            if tribe is Tribe.ALL:
                continue

            tribe_seen_before = False

            for old_res in game.log_by_type[MonsterSummonedResult]:
                if old_res.id == res.id:
                    continue

                if old_res.monster.controller_id != self.controller_id:
                    continue

                if Tribe.ALL in old_res.monster.template.tribes:
                    continue

                if old_res.monster.has_tribe(tribe):
                    tribe_seen_before = True
                    break

            if not tribe_seen_before:
                return (
                    SetVar(var=self.generated_card, value=GENERATE_CARD("Thrashing Machine"))
                    >> self.generated_card.buff(cost=-1, attack=-1, hp=-1)
                    >> self.generated_card.to_hand()
                )

        return None


@artifact(32)
class Seedlings(Artifact):
    name = "Seedlings"
    rarity = ArtifactRarity.LEGENDARY

    _dustpile_targets = DUSTPILE & IS_MONSTER & NON_TOKEN

    turn_end = Check(
        (COUNT(_dustpile_targets) >= 6)
        & (EMPTY_SLOTS(BOARD) > 0)
    ).to(
        _dustpile_targets[:6].erase()
        >> GENERATE_CARD("Red Flower").summon()
    )


@artifact(34)
class DarkFountain(Artifact):
    name = "Dark Fountain"
    rarity = ArtifactRarity.TOKEN

    generated_card: Var[Card] = Var(Card)

    def _gain_counter(self):
        yield SELF.update_artifact_counter(+1)

        if self.counter < 20:
            return None

        for _ in range(3):
            yield (
                SetVar(
                    var=DarkFountain.generated_card,
                    value=(
                        (
                            CARD_LIBRARY
                            & IS_MONSTER
                            & EXPANSION(Expansion.DELTARUNE)
                            & (RARITY <= EPIC)
                        )
                        >> RANDOM(1)
                        >> GENERATE_CARD()
                    ),
                )
                >> DarkFountain.generated_card.buff(cost=-2, attack=+2, hp=+2)
                >> DarkFountain.generated_card.to_deck()
            )

        yield SELF.transform_artifact(ARTIFACT_BY_NAME("Dark World"))

        return None

    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.template.rarity is CardRarity.TOKEN:
            return None

        for old_res in game.log_by_type[CardPlayedResult]:
            if old_res.id == res.id:
                continue

            if old_res.player_id != self.controller_id:
                continue

            if old_res.card.template.id == res.card.template.id:
                return None

        return self._gain_counter()


@artifact(35)
class Criticals(Artifact):
    name = "Criticals"
    rarity = ArtifactRarity.LEGENDARY

    turn_start = Check(YOU.turn % 6 == 0).to(
        ((BOARD | HAND | DECK) & IS_MONSTER).buff(attack=+1)
    )


@artifact(39)
class Reverberation(Artifact):
    name = "Reverberation"
    rarity = ArtifactRarity.LEGENDARY

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.controller_id != self.controller_id:
            return None

        monster = game.entity(res.monster.id)

        if not monster.has_ability(Ability.TURBO):
            return None

        return monster.actions.trigger_ability(TURBO)


@artifact(43)
class UltimateFusion(Artifact):
    name = "Ultimate Fusion"
    rarity = ArtifactRarity.LEGENDARY
    initial_counter = 7

    _thrashing_parts = (
        CARD_LIBRARY
        & IS_MONSTER
        & HAS_TRIBE(Tribe.THRASHING_PART)
        & ~HAS_TRIBE(Tribe.ALL)
    )

    turn_start = Check(
        (YOU.turn % 2 == 0)
        & (YOU.turn <= 15)
    ).to(
        HAND.last().to_deck(pos='top')
        >> GENERATE_CARD(
            (_thrashing_parts >> SORT_BY(COST))[(YOU.turn // 2) - 1]
        ).to_hand()
    )

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_tribe(Tribe.THRASHING_PART):
            return None

        if res.monster.has_tribe(Tribe.ALL):
            return None

        for old_res in game.log:
            if not isinstance(old_res, MonsterSummonedResult):
                continue

            if old_res.id == res.id:
                continue

            if old_res.monster.controller_id != self.controller_id:
                continue

            if old_res.monster.template.id == res.monster.template.id:
                return None

        return SELF.update_artifact_counter(-1)

    turn_end = Check(SELF.counter == 0).to(
        GENERATE_CARD("Final Gambit!").to_deck(pos='top')
        >> SELF.toggle_artifact(False)
    )


@artifact(46)
class FreeKromer(Artifact):
    name = "FREE KROMER"
    rarity = ArtifactRarity.LEGENDARY

    turn_start = Check(SELF.counter <= 3).to(
        Check(COUNT(HAND) >= MAX_HAND_SIZE).to(
            HAND.last().to_deck()
        )
        >> GENERATE_CARD("Irresistible Deal").to_hand()
    )

    turn_end = Check(HAND & (TEMPLATE_NAME == "Irresistible Deal")).to(
        Cast(
            card=GENERATE_CARD("BIG SHOT!!!"),
            controller=YOU,
        )
    )


@artifact(48)
class Dealmaker(Artifact):
    name = "Dealmaker"
    rarity = ArtifactRarity.LEGENDARY

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.template.rarity is CardRarity.TOKEN:
            return None

        if res.monster.cost <= 0:
            return None

        return (
            SELF.update_artifact_counter(+1)
            >> Check(SELF.counter >= 3).to(
                SELF.update_artifact_counter(-3)
                >> YOU.earn_gold(1)
            )
        )


@artifact(49)
class PuppetScarf(Artifact):
    name = "Puppet Scarf"
    rarity = ArtifactRarity.LEGENDARY

    turn_end = (
        ALLY_MONSTERS
        & ~HAS_KEYWORD(TRANSPARENCY)
    ).swap_stats()


@artifact(50)
class ThornRing(Artifact):
    name = "Thorn Ring"
    rarity = ArtifactRarity.LEGENDARY

    shock = Check(
        TRIGGER_CARD & NON_TOKEN
    ).to(
        SELF.update_artifact_counter(+1)
    )

    turn_start = Check(SELF.counter >= 8).to(
        SELF.update_artifact_counter(-8)
        >> YOU.earn_gold(10)
    )


@artifact(51)
class EliteSoldiers(Artifact):
    name = "Elite Soldiers"
    rarity = ArtifactRarity.LEGENDARY

    monster: Var[Card] = Var(Card)

    _targets = DUSTPILE & IS_MONSTER & NON_GENERATED & NON_DT

    turn_end = Check(
        (YOU.turn % 4 == 0)
        & (COUNT(_targets) > 0)
        & (COUNT(HAND) < MAX_HAND_SIZE)
    ).to(
        SetVar(var=monster, value=_targets >> MAX(COST))
        >> monster.buff(cost=-1, attack=+1, hp=+1)
        >> monster.to_hand()
    )


@artifact(52)
class SeamsSeap(Artifact):
    name = "Seam's Seap"
    rarity = ArtifactRarity.LEGENDARY

    generated_card: Var[TargetSelector] = Var(TargetSelector)
    last_counter_turn: StateVar[int | None] = StateVar(default=None)

    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if game.players[self.controller_id].gold != 0:
            return None

        return OncePerTurn(
            self.last_counter_turn,
            SELF.update_artifact_counter(+1),
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


@artifact(71)
class GoldWidow(Artifact):
    name = "Gold Widow"
    rarity = ArtifactRarity.LEGENDARY

    generated_card: Var[TargetSelector] = Var(TargetSelector)

    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.cost < 6:
            return None

        spend_result = yield YOU.spend_gold(1)
        if not spend_result.success:
            return None

        yield SELF.update_artifact_counter(+1)

        yield GENERATE_CARD("Spider").summon()

        if self.counter < 5:
            return None

        yield SELF.update_artifact_counter(-5)

        yield SetVar(
            var=self.generated_card,
            value=GENERATE_CARD("Spider Donut"),
        )
        yield self.generated_card.set_stats(cost=0)
        yield self.generated_card.to_hand()

        return None


@artifact(75)
class PetalFeather(Artifact):
    name = "Petal Feather"
    rarity = ArtifactRarity.LEGENDARY

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.player_id != self.controller_id:
            return None

        monster = game.entity(res.monster_id)
        return Check(
            COUNT(
                CARDS_PLAYED(
                    player=YOU,
                    scope=THIS_TURN
                )
                & IS_MONSTER
            ) == 3
        ).to(
            monster.actions.buff(attack=+1, hp=+1)
            >> monster.actions.add_keyword(HASTE)
        )
