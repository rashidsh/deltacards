from deltacards.dsl.api import *


@card(808)
class Clover(Monster):
    magic = GENERATE_CARD("The First Round").to_hand()

    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.SET,
            source=self,
            description="Your Rounds cost 0",
            applies=lambda q: (
                q.card.controller_id == self.controller_id
                and q.card.has_tribe(Tribe.ROUND)
            ),
            apply=lambda cost, q: 0,
        )


@card(809)
class Penilla(Monster):
    your_monster: Var[Card] = Var(Card)
    enemy_monster: Var[Card] = Var(Card)

    magic = (
        SetVar(var=your_monster, value=(DECK & IS_MONSTER).first())
        >> SetVar(var=enemy_monster, value=(OPPONENT_DECK & IS_MONSTER).first())
        >> YOU.draw(your_monster)
        >> OPPONENT.draw(enemy_monster)
        >> SELF.schedule_delay_effect()
    )

    delay = Check(your_monster & HAND).to(
        SwapCards(card1=your_monster, card2=enemy_monster)
    )


@card(810)
class Decibat(Monster):
    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.card.template.rarity is CardRarity.TOKEN:
            return None

        return game.player(res.player_id).actions.hit(3)


@card(811)
class Dunebud(Monster):
    shock = GENERATE_CARD("Dunebud").summon()

    turn_end = SELF.toggle_ability(SHOCK, False)


@card(812)
class Flameguy(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.kill().to(
        YOU.draw_next() * 2
    )


@card(814)
class Rorrim(Monster):
    copied_card: Var[Card] = Var(Card)

    dust = Check(KILLER & IS_MONSTER).to(
        Program(3).to(
            SetVar(var=copied_card, value=KILLER >> COPY())
            >> copied_card.set_base_stats(attack=4, hp=4)
            >> copied_card.add_keyword(TAUNT)
            >> copied_card.summon()
        )
    )


@card(815)
class DalvsWardrobe(Monster):
    generated_card: Var[Card] = Var(Card)

    _bonus = COUNT(
        MONSTERS_DIED(scope=THIS_TURN)
        & NON_TOKEN
        & (MONSTER_ID != SELF.id)
    )

    dust = (
        SetVar(var=generated_card, value=GENERATE_CARD("Pops"))
        >> generated_card.buff(attack=_bonus, hp=_bonus)
        >> generated_card.summon()
    )


@card(824)
class Dalv(Monster):
    shock = (
        GENERATE_CARD("Lightning Bolt").summon()
        >> SELF.toggle_ability(SHOCK, False)
    )

    turn_end = SELF.toggle_ability(SHOCK, True)


@card(825)
class LightningBolt(Monster):
    dust = Check(TURN_PLAYER.id == YOU.id).to(
        (ENEMY_MONSTERS >> MIN(HP)).hit(2)
    )


@card(826)
class Starlo(Monster):
    magic = GENERATE_CARD("Quick Draw").to_hand()

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.turn_player_id != self.controller_id:
            return None

        if not res.monster.has_keyword(WANTED):
            return None

        return GENERATE_CARD("Quick Draw").to_hand()


@card(828)
class Ceroba(Monster):
    targets = ENEMY_MONSTERS

    magic = TARGET.paralyze()

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        if res.player_id == self.controller_id:
            return None

        if res.turn_player_id == self.controller_id:
            return None

        return OPPONENT.buff(hp=-2)

    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.turn_player_id == self.controller_id:
            return None

        attacker = game.entity(res.attacker_id)
        if not isinstance(attacker, Monster):
            return None

        if attacker.controller_id == self.controller_id:
            return None

        return OPPONENT.buff(hp=-2)


@card(829)
class Chujin(Monster):
    magic = (
        YOU.add_artifact(ARTIFACT_BY_NAME("Unstable Serum"))
        >> ENEMY_MONSTERS.kill()
        >> HAND.buff(cost=-1)
        >> DrawUpTo(7)
    )


@card(830)
class Well(Monster):
    turn_end = Program(1).to(
        (
            (
                CARD_LIBRARY
                & EXPANSION(Expansion.UTY)
                & (RARITY == LEGENDARY)
            )
            >> RANDOM(1)
            >> GENERATE_CARD()
        ).to_hand()
    )


@card(831)
class TNTMan(Monster):
    targets = ALL_PLAYERS | ALL_MONSTERS

    magic = TARGET.hit(1)

    bullseye = (ALLIES | ENEMIES).hit(4)


@card(832)
class TallMiner(Monster):
    shock = Check(TRIGGER_CARD.template_name != "Crystal Shard").to(
        GENERATE_CARD("Crystal Shard").to_hand()
    )


@card(833)
class Gamer(Monster):
    _effect = (
        (ENEMY_MONSTERS >> MIN(HP)).hit(2)
        >> OPPONENT.hit(1)
    )

    magic = _effect
    bullseye = _effect


@card(834)
class Drinki(Monster):
    bullseye = SELF.heal(SELF.max_hp)


@card(835)
class Rockman(Monster):
    bullseye = GENERATE_CARD("Pebble").summon()


@card(836)
class FoodEnjoyer(Monster):
    chosen_card: Var[TargetSelector] = Var(TargetSelector)

    magic = YOU.choose(HAND).to(
        SetVar(var=chosen_card, value=CHOICE_SELECTED)
        >> SELF.schedule_delay_effect()
    )

    delay = Check(chosen_card & HAND).to(
        chosen_card.erase().to(
            SELF.heal(SELF.max_hp)
        )
    )


@card(837)
class ElBailador(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        attacker = game.entity(res.attacker_id)
        if not isinstance(attacker, Monster):
            return None

        return attacker.actions.swap_stats()


@card(839)
class Icemeter(Monster):
    turn_end = SELF.buff(
        hp=COUNT(GOLD_SPENT(player=YOU, scope=THIS_TURN, reason='play_spell'))
    )


@card(840)
class Bowll(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="This takes +2 DMG from enemy monsters and spells",
            applies=lambda q: (
                q.target is self
                and isinstance(q.source, (Monster, Spell))
                and q.source.controller_id != self.controller_id
            ),
            apply=lambda damage, q: damage + 2,
        )


@card(841)
class FrostIgloo(Monster):
    generated_card: Var[Card] = Var(Card)

    turn_start = (
        SetVar(var=generated_card, value=GENERATE_CARD("Frostermit"))
        >> generated_card.set_base_stats(hp=SELF.hp)
        >> SELF.turn_into(generated_card)
    )


@card(843)
class Cardmaster(Monster):
    magic = For(
        OPPONENT.gold // 3,
        YOU.earn_gold(2) >> GENERATE_CARD("Draft").to_hand()
    )


@card(846)
class Giftshopper(Monster):
    dust = (
        (HAND >> MAX(COST))
        | (OPPONENT_HAND >> MAX(COST))
    ).buff(cost=-4)


@card(847)
class FortuneTeller(Monster):
    magic = YOU.choose(OPPONENT_DECK[:3]).to(
        CHOICE_SELECTED.buff(cost=+2)
    )


@card(849)
class SnakeMiner(Monster):
    _effect = GENERATE_CARD("Crystal Shard").to_hand()

    delay = _effect
    bullseye = _effect


@card(850)
class MinesSign(Monster):
    turn_end = GENERATE_CARD("Mine", controller=OPPONENT).to_deck(controller=OPPONENT)


@card(851)
class Minecart(Monster):
    _effect = GENERATE_CARD("Crystal Shard").to_hand()

    dust = _effect
    turn_start = _effect


@card(852)
class Searby(Monster):
    draw_result: Var[StepResult] = Var(StepResult)

    magic = FRONT(SELF).hit(5)

    bullseye = (
        YOU.draw_next().store_result(draw_result).to(
            Buff(target=draw_result.card_id, cost=-2)
        )
    )


@card(853)
class ChujinTombstone(Monster):
    dustpile_cards: Var[TargetSelector] = Var(TargetSelector)
    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=dustpile_cards,
            value=(
                DUSTPILE
                & IS_MONSTER
                & NON_DT
                & NON_GENERATED
            ) >> DISTINCT(TEMPLATE_ID) >> RANDOM(3)
        )
        >> SetVar(var=copied_cards, value=dustpile_cards >> COPY())
        >> dustpile_cards.erase()
        >> copied_cards.buff(cost=-3)
        >> copied_cards.to_hand()
    )


@card(859)
class FakeTrain(Monster):
    copied_card: Var[Card] = Var(Card)

    bullseye = (
        SetVar(var=copied_card, value=SELF >> COPY())
        >> copied_card.buff(
            cost=SELF.buffs.cost,
            attack=SELF.buffs.attack + 2,
            hp=SELF.buffs.max_hp
        )
        >> copied_card.summon()
    )

    turn_end = SELF.toggle_ability(BULLSEYE, False)


@card(862)
class ArcadeSamurai(Monster):
    magic = GENERATE_CARD("Arcade Bat", controller=OPPONENT).summon(
        controller=OPPONENT
    ) * 2


@card(864)
class Axis(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        if res.killed:
            return None

        yield SELF.set_base_stats(attack=SELF.base.attack + 1)

        if self.base.attack >= 6:
            yield Cast(
                card=GENERATE_CARD("Overheat"),
                controller=YOU,
                effect_target=SELF
            )

        return None


@card(865)
class Gilbert(Monster):
    _effect = GENERATE_CARD("Hard Hat").to_hand()

    bullseye = _effect
    dust = _effect


@card(866)
class HardHat(Spell):
    targets = ALL_MONSTERS

    magic = TARGET.add_keyword(ARMOR)


@card(867)
class OrganPiano(Monster):
    dust = GENERATE_CARD("Lightning Bolt").to_hand()


@card(868)
class Pancakes(Monster):
    targets = ALL_MONSTERS

    heal_result: Var[StepResult] = Var(StepResult)

    magic = TARGET.heal(TARGET.max_hp).store_result(heal_result).to(
        YOU.heal(heal_result.amount)
    )


@card(869)
class VengefulVirgil(Monster):
    bullseye = ADJACENT(TARGET).add_keyword(WANTED)


@card(870)
class Angie(Monster):
    generated_card: Var[Card] = Var(Card)

    shock = (
        SetVar(var=generated_card, value=GENERATE_CARD("Gemstone"))
        >> generated_card.set_stats(cost=0)
        >> generated_card.to_hand()
    )

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.turn_player_id != self.controller_id:
            return None

        if res.monster.controller_id == self.controller_id:
            return None

        return (ENEMY_MONSTERS >> RANDOM(1)).set_stats(hp=1)


@card(872)
class Bryan(Monster):
    magic = GENERATE_CARD("Dynamite Stick").summon()

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.turn_player_id != self.controller_id:
            return None

        if res.monster.controller_id == self.controller_id:
            return None

        return GENERATE_CARD("Dynamite Stick").summon()


@card(873)
class Mo(Monster):
    generated_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=generated_cards,
            value=(
                CARD_LIBRARY
                & NON_DT
                & NON_TOKEN
                & (COST >= 5)
            ) >> RANDOM(3) >> GENERATE_CARD()
        )
        >> generated_cards.buff(cost=-3)
        >> generated_cards.to_hand()
        >> SELF.schedule_delay_effect()
    )

    delay = (generated_cards & HAND).erase()


@card(878)
class CerobaKetsukane(Monster):
    left_mirror: Var[Card] = Var(Card)
    right_mirror: Var[Card] = Var(Card)

    magic = (
        SetVar(var=left_mirror, value=GENERATE_CARD("Golden Mirror"))
        >> left_mirror.summon(pos=SELF.pos - 1).to(
            left_mirror.catch(FRONT(left_mirror))
        )
        >> SetVar(var=right_mirror, value=GENERATE_CARD("Golden Mirror"))
        >> right_mirror.summon(pos=SELF.pos + 1).to(
            right_mirror.catch(FRONT(right_mirror))
        )
    )

    turn_start = SELF.set_status(DODGE, value=SELF.status(DODGE) + 1)


@card(879)
class GoldenMirror(Monster):
    released_card: Var[Card] = Var(Card)

    dust = SELF.release_caught_card(released_card).to(
        released_card.summon(controller=released_card.controller)
    )

    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="Non-TOKEN spells in the enemy hand have +1 COST",
            applies=lambda q: (
                isinstance(q.card, Spell)
                and q.card.zone is CardZone.HAND
                and q.card.controller_id != self.controller_id
                and q.card.template.rarity is not CardRarity.TOKEN
            ),
            apply=lambda cost, q: cost + 1,
        )


@card(945)
class ArcadeMewMew(Monster):
    magic = Check(FRONT(SELF) & NON_DT).to(
        FRONT(SELF).halve_stats(round_up=False)
        >> (FRONT(SELF) >> EXACT_COPY()).summon()
    )


@card(947)
class WildRevolver(Spell):
    targets = ALL_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)
    monster_to_buff: Var[TargetSelector] = Var(TargetSelector)

    magic = TARGET.hit(6).store_result(hit_result).to(
        For(
            hit_result.excess_damage,
            (
                SetVar(
                    var=monster_to_buff,
                    value=(HAND & IS_MONSTER) >> RANDOM(hit_result.excess_damage),
                )
                >> monster_to_buff.buff(cost=-1, attack=+1, hp=+1)
                >> monster_to_buff.add_keyword(WANTED)
            )
        )
    )


@card(948)
class Blackjack(Monster):
    magic = YOU.choose(DECK[:6]).to(
        CHOICE_SELECTED.turn_into(
            GENERATE_CARD("Wild Revolver")
        )
    )


@card(949)
class Moray(Monster):
    magic = ENEMY_MONSTERS.hit(2)

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if not res.monster.has_keyword(WANTED):
            return None

        return ENEMY_MONSTERS.hit(1)


@card(950)
class PlagueDoctor(Monster):
    targets = ALLY_SLOTS

    magic = TARGET.enchant(
        ENCHANTMENT_BY_NAME('the-cure')
    )


@card(954)
class Violetta(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(
            var=generated_card,
            value=GENERATE_CARD("Blue Rose")
        )
        >> generated_card.buff(
            cost=-COUNT(ALLY_MONSTERS & ~SELF)
        )
        >> generated_card.to_hand()
    )
