import math

from deltacards.dsl.api import *
from deltacards.model.artifacts import Artifact, ArtifactRarity, artifact


@artifact(24)
class TornNotebook(Artifact):
    name = "Torn Notebook"
    rarity = ArtifactRarity.TOKEN

    debuff_target: Var[Card] = Var(Card)

    turn_start = (
        SetVar(
            var=debuff_target,
            value=(ENEMY_MONSTERS & ~HAS_KEYWORD(KR)) >> MAX(ATTACK),
        )
        >> debuff_target.add_keyword(KR)
        >> debuff_target.buff(attack=-1)
    )


@artifact(25)
class Genocide(Artifact):
    name = "Genocide"
    rarity = ArtifactRarity.TOKEN

    turn_start = GENERATE_CARD("Real Knife").to_hand()
    turn_end = (HAND & (TEMPLATE_NAME == "Real Knife")).erase()


@artifact(33)
class Save(Artifact):
    name = "Save"
    rarity = ArtifactRarity.TOKEN

    turn_end = Check(SELF.counter >= 20).to(
        SELF.update_artifact_counter(-20)
        >> Check(EMPTY_SLOTS(BOARD) > 0).to(
            NEXT_LOST_SOUL.summon(attack=1, hp=1),
            else_=NEXT_LOST_SOUL.trigger_ability(DUST)
        )
    )

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.has_tribe(Tribe.LOST_SOUL):
            return None

        counters_to_add = res.monster.cost
        if counters_to_add <= 0:
            return None

        if res.monster.is_generated or res.monster.controller_id != self.controller_id:
            counters_to_add = math.ceil(counters_to_add / 2)

        return SELF.update_artifact_counter(counters_to_add)


@artifact(37)
class TrueJustice(Artifact):
    name = "True Justice"
    rarity = ArtifactRarity.TOKEN

    _effect = Check(
        (SELF.counter > 0)
        & (
            (COUNT(ENEMY_MONSTERS) >= 1)
            | (YOU.hp < OPPONENT.hp)
        )
    ).to(
        SELF.update_artifact_counter(-1)
        >> (ENEMY_MONSTERS >> MIN(HP)).hit(1)
        >> Check(YOU.hp < OPPONENT.hp).to(
            OPPONENT.hit(1)
        )
    )

    turn_end = _effect
    shock = _effect


@artifact(38)
class Economics(Artifact):
    name = "Economics"
    rarity = ArtifactRarity.TOKEN

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.monster.controller_id != self.controller_id:
            return None

        if self.counter <= 0:
            return None

        return (
            YOU.spend_gold(1).to(
                SELF.update_artifact_counter(-1)
                >> game.entity(res.monster.id).actions.buff(attack=+1, hp=+2)
            )
        )


@artifact(44)
class Hail(Artifact):
    name = "Hail"
    rarity = ArtifactRarity.TOKEN

    turn_start = Check(SELF.counter > 0).to(
        SELF.update_artifact_counter(-1)
        >> ALL_MONSTERS.hit(1)
    )

    def iter_modifiers(self, game):
        if not self.active:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="Paralyzed monsters take +1 DMG.",
            applies=lambda q: (
                isinstance(q.target, Monster)
                and q.target.get_status(CardStatusId.PARALYZED) > 0
            ),
            apply=lambda damage, q: damage + 1,
        )


@artifact(45)
class Freedom(Artifact):
    name = "Freedom"
    rarity = ArtifactRarity.TOKEN

    turn_start = Check(SELF.counter >= 7).to(
        SELF.update_artifact_counter(-7)
        >> GENERATE_CARD("Chaos Bomb").to_hand()
    )

    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if res.card.controller_id != self.controller_id:
            return None

        if not res.is_played:
            return None

        if res.card.template.rarity is CardRarity.TOKEN:
            return None

        if res.card.template.soul_id is None:
            return None

        if res.card.template.soul_id == game.player(self.controller_id).soul.id:
            return None

        for old_res in game.log_by_type[SpellCastResult]:
            if old_res.id == res.id:
                continue

            if old_res.player_id != self.controller_id:
                continue

            if not old_res.is_played:
                continue

            if old_res.card.template.rarity is CardRarity.TOKEN:
                continue

            if old_res.card.template.soul_id == res.card.template.soul_id:
                return None

        return SELF.update_artifact_counter(+1)


@artifact(47)
class Endgame(Artifact):
    name = "Endgame"
    rarity = ArtifactRarity.TOKEN

    # This artifact is implemented via `SwitchPiece` macro.


@artifact(55)
class ToyKnife(Artifact):
    name = "Toy Knife"
    rarity = ArtifactRarity.TOKEN

    turn_end = Check(
        ~EXISTS(HAND & (TEMPLATE_NAME == "Change of Winds"))
    ).to(
        GENERATE_CARD("Change of Winds").to_deck(pos='top')
    )


@artifact(56)
class ToughGlove(Artifact):
    name = "Tough Glove"
    rarity = ArtifactRarity.TOKEN

    turn_start = Check(YOU.turn % 2 == 0).to(
        Check(COUNT(HAND) < MAX_HAND_SIZE).to(
            GENERATE_CARD("Draft").to_hand(),
            else_=GENERATE_CARD("Draft").to_deck()
        )
    )


@artifact(57)
class BalletShoes(Artifact):
    name = "Ballet Shoes"
    rarity = ArtifactRarity.TOKEN

    turn_end = YOU.earn_gold(1)


@artifact(58)
class BurntPan(Artifact):
    name = "Burnt Pan"
    rarity = ArtifactRarity.TOKEN

    turn_end = (
        YOU.heal(1)
        >> Check(COUNT(ALLY_MONSTERS & DAMAGED) > 0).to(
            (ALLY_MONSTERS & DAMAGED).heal(2),
            else_=(ALLY_MONSTERS >> RIGHTMOST).buff(attack=+1, hp=+1)
        )
    )


@artifact(59)
class EmptyGun(Artifact):
    name = "Empty Gun"
    rarity = ArtifactRarity.TOKEN

    turn_end = (ENEMY_MONSTERS >> MIN(HP)).hit(1)


@artifact(60)
class WornDagger(Artifact):
    name = "Worn Dagger"
    rarity = ArtifactRarity.TOKEN

    turn_end = Check(
        (SELF.counter >= 5)
        & (EMPTY_SLOTS(BOARD) > 0)
    ).to(
        SELF.update_artifact_counter(-5)
        >> NEXT_LOST_SOUL.summon(attack=2, hp=2)
    )

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.has_tribe(Tribe.LOST_SOUL):
            return None

        return SELF.update_artifact_counter(+1)


@artifact(61)
class Will(Artifact):
    name = "Will"
    rarity = ArtifactRarity.TOKEN

    game_start = GENERATE_CARD("Recruitment").to_hand()

    turn_end = Check(YOU.turn == 7).to(
        ALLY_MONSTERS.buff(attack=+1, hp=+1)
    )


@artifact(62)
class UndergroundArmy(Artifact):
    name = "Underground Army"
    rarity = ArtifactRarity.TOKEN

    _targets = DUSTPILE & IS_MONSTER & NON_GENERATED & NON_DT

    turn_end = Check(
        (EMPTY_SLOTS(BOARD) > 0)
        & (COUNT(_targets) > 0)
    ).to(
        (_targets >> MAX(COST) >> COPY()).summon()
        >> (_targets >> MAX(COST)).erase()
    )


@artifact(63)
class ImminentShowdown(Artifact):
    name = "Imminent Showdown"
    rarity = ArtifactRarity.TOKEN
    initial_counter = 3

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.template.name != "GIGA Queen":
            return None

        if self.counter > 0:
            dead_monster = game.entity(res.monster.id)

            return (
                SELF.update_artifact_counter(-1)
                >> dead_monster.actions.to_deck()
                >> dead_monster.actions.set_base_stats(
                    cost=res.monster.base.cost + 1,
                    attack=res.monster.base.attack + 2,
                    hp=res.monster.base.hp + 2,
                )
            )

        else:
            return (
                GENERATE_CARD("Detachable Hands").to_hand()
                >> SELF.toggle_artifact(False)
            )


@artifact(64)
class UnstableSerum(Artifact):
    name = "Unstable Serum"
    rarity = ArtifactRarity.TOKEN

    turn_end = TakeFatigueDamage(player=YOU)


@artifact(65)
class DarkWorld(Artifact):
    name = "Dark World"
    rarity = ArtifactRarity.TOKEN
    initial_counter = 20

    generated_card: Var[TargetSelector] = Var(TargetSelector)

    turn_start = While(
        (COUNT(HAND) < MAX_HAND_SIZE)
        & (SELF.counter >= 2),

        SELF.update_artifact_counter(-2)
        >> SetVar(
            var=generated_card,
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
        >> generated_card.buff(cost=-2, attack=+2, hp=+2)
        >> generated_card.to_hand()
    )


@artifact(67)
class ConstrictingDarkness(Artifact):
    name = "Constricting Darkness"
    rarity = ArtifactRarity.TOKEN
    initial_counter = 4

    generated_card: Var[TargetSelector] = Var(TargetSelector)

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.template.name != "Titan Spawn":
            return None

        if res.turn_player_id == self.controller_id:
            return None

        return Check(
            COUNT(
                MONSTERS_DIED(
                    controller=YOU,
                    scope=THIS_TURN,
                    turn_player=OPPONENT,
                )
                & (TEMPLATE_NAME == "Titan Spawn")
            ) == 1
        ).to(
            SELF.update_artifact_counter(-2)
            >> Check(SELF.counter == 0).to(
                SELF.toggle_artifact(False)
            )
        )

    turn_end = Check(EMPTY_SLOTS(BOARD) > 0).to(
        SELF.update_artifact_counter(+1)
        >> SetVar(
            var=generated_card,
            value=GENERATE_CARD("Titan Spawn"),
        )
        >> generated_card.summon(attack=SELF.counter, hp=SELF.counter)
        >> Check(
            (SELF.counter == 7)
            & ~EXISTS(YOU & HAS_ARTIFACT("The Roaring"))
        ).to(
            YOU.add_artifact(ARTIFACT_BY_NAME("The Roaring"))
        )
    )


@artifact(68)
class TheRoaring(Artifact):
    name = "The Roaring"
    rarity = ArtifactRarity.TOKEN

    generated_card: Var[TargetSelector] = Var(TargetSelector)

    turn_start = Check(
        EMPTY_SLOTS(BOARD) > 0
    ).to(
        SetVar(var=generated_card, value=GENERATE_CARD("Titan"))
        >> generated_card.add_keyword(CHARGE)
        >> generated_card.add_keyword(INVULNERABLE)
        >> generated_card.summon()
    )


@artifact(69)
class DarkZone(Artifact):
    name = "DARK ZONE"
    rarity = ArtifactRarity.TOKEN
    initial_counter = 25

    generated_card: Var[TargetSelector] = Var(TargetSelector)

    @on_event(GoldSpentResult)
    def on_gold_spent(self, res: GoldSpentResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card is None:
            return None

        return (
            SELF.update_artifact_counter(-res.amount)
            >> Check(SELF.counter == 0).to(
                SELF.update_artifact_counter(+30)
                >> Check(EMPTY_SLOTS(BOARD) > 0).to(
                    SetVar(
                        var=self.generated_card,
                        value=GENERATE_CARD("Pumpkin Head"),
                    )
                    >> self.generated_card.summon()
                    >> self.generated_card.force_attack(ENEMY_MONSTERS)
                )
            )
        )


@artifact(70)
class OddController(Artifact):
    name = "Odd Controller"
    rarity = ArtifactRarity.TOKEN
    initial_counter = 1

    turn_start = SELF.update_artifact_counter(+1)

    turn_end = (
        For(
            SELF.counter,
            (ALLY_MONSTERS >> RANDOM(1)).buff(attack=+1, hp=+1),
        )
        >> Check(
            COUNT(CARDS_PLAYED(player=YOU, scope=THIS_TURN) & IS_MONSTER)
            < SELF.counter
        ).to(
            SELF.toggle_artifact(False)
        )
    )


@artifact(72)
class Stick(Artifact):
    name = "Stick"
    rarity = ArtifactRarity.TOKEN

    turn_start = Check(YOU.turn % 4 == 0).to(
        GENERATE_CARD("Throw the Stick").to_hand()
    )


@artifact(79)
class ShatteredRose(Artifact):
    name = "Shattered Rose"
    rarity = ArtifactRarity.TOKEN

    support = ATTACKER.buff(attack=+1, hp=+1)

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        killer = game.entity(res.killer_id)
        if not isinstance(killer, Monster):
            return None

        if res.killer.controller_id != self.controller_id:
            return None

        if res.killer_id == res.monster_id:
            return None

        return (
            SELF.update_artifact_counter(+1)
            >> Check(
                SELF.counter >= SELF.quest_goal
            ).to(
                GENERATE_CARD("Ice Crystal").to_hand()
                >> SELF.update_artifact_counter(-SELF.counter)
            )
        )
