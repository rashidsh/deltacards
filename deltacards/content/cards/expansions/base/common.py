from deltacards.dsl.api import *


@card(7)
class Loox(Monster):
    targets = ALLIES | ENEMIES

    magic = (
        TARGET.hit(1)
        >> Check(TARGET & ALLIES).to(
            SELF.buff(attack=+1)
        )
    )


@card(14)
class Jerry(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="Takes 1 less DMG from monsters costing 4 or less GOLD",
            applies=lambda q: (
                q.target is self
                and isinstance(q.source, Monster)
                and q.source.cost <= 4
            ),
            apply=lambda damage, q: damage - 1,
        )


@card(17)
class KnightKnight(Monster):
    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if res.attacker_dead:
            return None

        return SELF.heal(res.damage_to_defender)


@card(18)
class Pyrope(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return OPPONENT.hit(3)


@card(21)
class Tsunderplane(Monster):
    magic = ENEMY_MONSTERS.hit(1) >> OPPONENT.hit(3)


@card(23)
class Migospel(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.buff(hp=+3)


@card(25)
class Astigmatism(Monster):
    targets = ALLIES | ENEMIES

    magic = TARGET.hit(2)

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.killer_id != self.id:
            return None

        return GENERATE_CARD("Loox").to_hand()


@card(27)
class Whimsalot(Monster):
    magic = (HAND & IS_MONSTER).buff(
        cost=-1,
        attack=-1,
        hp=-1,
        min_attack=1,
        min_hp=1,
    )


@card(29)
class Bomb(Monster):
    targets = ALLIES | ENEMIES

    magic = ((HAND & NON_GENERATED) >> MIN(COST)).erase().to(
        TARGET.hit(3)
    )


@card(31)
class Snowman(Monster):
    generated_card: Var[Card] = Var(Card)

    dust = (
        SetVar(var=generated_card, value=SELF >> COPY())
        >> generated_card.set_base_stats(
            cost=SELF.base.cost - 1,
            hp=SELF.base.hp - 1
        )
        >> generated_card.to_hand()
    )


@card(102)
class SadCustomer(Monster):
    released_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (
            DUSTPILE
            & (COST <= 5)
            & (TEMPLATE_ID != SELF.template_id)
        ) >> MAX(COST, n=2)
    ).to(
        SELF.catch(CHOICE_SELECTED)
    )

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.summon(controller=released_card.controller)
    )


@card(107)
class WaterCooler(Monster):
    turn_end = ALLIES.heal(2)


@card(108)
class Rock(Monster):
    dust = GENERATE_CARD("Pebble").summon()


@card(113)
class Igloo(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.to_hand()


@card(116)
class SmallBird(Monster):
    magic = Check(ALL_MONSTERS & HAS_KEYWORD(TAUNT)).to(
        SELF.add_keyword(CHARGE)
    )


@card(122)
class Janitor(Monster):
    magic = LEFT_OF(SELF).buff(hp=+1) >> RIGHT_OF(SELF).buff(attack=+1)


@card(125)
class HeatsFlamesman(Monster):
    turn_end = (ALL_PLAYERS | (ALL_MONSTERS & ~SELF)).hit(1)


@card(138)
class Ferry(Monster):
    dust = YOU.earn_gold(2)


@card(140)
class PoliticsBear(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id == self.controller_id:
            return SELF.buff(hp=+1)

        return SELF.buff(attack=+1)


@card(141)
class GiftBear(Monster):
    turn_end = GENERATE_CARD("Gift").summon()


@card(142)
class BlueLaser(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        attacker = game.entity(res.attacker_id)
        if not isinstance(attacker, Monster):
            return None

        if attacker.controller_id == self.controller_id:
            return None

        return attacker.actions.hit(1)


@card(143)
class OrangeLaser(Monster):
    support = SELF.buff(attack=+1)


@card(148)
class Faun(Monster):
    targets = ENEMY_MONSTERS

    magic = (
        TARGET.buff(attack=-2)
        >> DISCOVER(NON_DT, NON_TOKEN, COST == TARGET.attack).to_hand()
    )


@card(163)
class MttFountain(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        return YOU.heal(res.amount)


@card(164)
class Lamp(Monster):
    dust = GENERATE_CARD("Snow Frisk").summon()


@card(165)
class Oni(Monster):
    need = EXISTS(
        HAND
        & IS_SPELL
        & NON_TOKEN
        & ANOTHER_SOUL_THAN(YOU)
    )

    magic = GENERATE_CARD("Charles").summon()


@card(166)
class CrazyBun(Monster):
    magic = (ALL_MONSTERS & ~SELF).hit(1)


@card(167)
class Receptionist1(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        return (HAND >> RANDOM(1)).buff(cost=-1)


@card(169)
class Bunbun(Monster):
    magic = GENERATE_CARD("Bun").summon()


@card(194)
class ShamblingMass(Monster):
    dust = For(
        5,
        effect=(ENEMY_MONSTERS >> RANDOM(1)).hit(1)
    )


@card(195)
class DogFood(Monster):
    magic = (HAND & HAS_TRIBE(Tribe.DOG)).buff(attack=+1, hp=+1)


@card(217)
class Mace(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.hit(3).to(
        OPPONENT.hit(3)
    )


@card(226)
class Microwave(Monster):
    targets = HAND

    magic = TARGET.erase()


@card(236)
class HotDogVulkin(Monster):
    targets = ENEMIES | ALLY_MONSTERS

    magic = Check(TARGET & ALLY_MONSTERS).to(
        TARGET.buff(attack=+3),
        else_=TARGET.hit(3)
    )


@card(238)
class ScriptBomb(Monster):
    draw_result: Var[StepResult] = Var(StepResult)

    dust = YOU.draw_next().store_result(draw_result).to(
        Buff(target=draw_result.card_id, cost=-2)
    )

    turn_start = SELF.trigger_ability(DUST) >> SELF.kill()


@card(243)
class Bench(Monster):
    magic = YOU.draw_next()


@card(244)
class FoxHead(Monster):
    magic = (
        (ENEMY_MONSTERS >> LEFTMOST).hit(1)
        >> (ENEMY_MONSTERS >> RIGHTMOST).hit(1)
    )


@card(247)
class DressLion(Monster):
    targets = ENEMY_MONSTERS & (ATTACK <= SELF.attack)

    turbo = SELF.buff(attack=+1)

    magic = TARGET.silence()


@card(253)
class BonePainting(Monster):
    targets = HAND & HAS_TRIBE(Tribe.DOG)

    magic = (
        TARGET.buff(attack=+1, hp=+1)
        >> TARGET.add_keyword(TAUNT)
    )


@card(400)
class Cogwheel(Monster):
    turn_end = (HAND >> MAX(COST)).to_deck() >> YOU.draw_next()


@card(401)
class Certificate(Monster):
    magic = YOU.choose(
        DISCOVER(IS_MONSTER, NON_DT, NON_TOKEN, HAS_KEYWORD(TAUNT), n=3)
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(402)
class BoneBox(Monster):
    magic = YOU.choose(
        DISCOVER(IS_SPELL, NON_TOKEN, COST <= 3, n=3)
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(403)
class Jukebox(Monster):
    copied_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (DUSTPILE & (TEMPLATE_ID != SELF.template_id)) >> RANDOM(3)
    ).to(
        SetVar(var=copied_card, value=CHOICE_SELECTED >> COPY())
        >> copied_card.buff(attack=+1, hp=+1)
        >> copied_card.to_deck()
    )


@card(404)
class DeflatedMascot(Monster):
    turn_end = YOU.earn_gold(1)


@card(405)
class Telescope(Monster):
    _effect = GENERATE_CARD("Scope").to_hand()

    magic = _effect
    turn_start = _effect

    turn_end = (HAND & (TEMPLATE_NAME == "Scope")).erase()


@card(406)
class SugarPot(Monster):
    targets = HAND & IS_MONSTER

    magic = TARGET.buff(attack=+2, hp=+2)


@card(420)
class SpikeTrap(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        if game.turn_player.id == self.controller_id:
            return None

        return ((ALLY_MONSTERS & ~SELF) >> RANDOM(1)).buff(attack=+1, hp=+1)


@card(433)
class Butterflies(Monster):
    dust = YOU.draw((DECK & IS_SPELL).first())


@card(437)
class ShyrensAgent(Monster):
    targets = ALLY_MONSTERS & DAMAGED

    excess_healing: Var[int] = Var(int)

    magic = (
        SetVar(
            var=excess_healing,
            value=GREATEST(7 - (TARGET.max_hp - TARGET.hp), 0)
        )
        >> TARGET.heal(7)
        >> FRONT(SELF).hit(excess_healing)
    )


@card(438)
class Battleflies(Monster):
    need = SPENT_GOLD_ON_SPELLS_LAST_TURN

    magic = SELF.buff(attack=+2)


@card(465)
class MTTTV(Monster):
    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        player = game.player(res.player_id)
        return player.opponent.actions.earn_gold(1)


@card(471)
class ChaosBlaster(Monster):
    magic = (
        YOU.hit(5)
        >> YOU.choose(
            DISCOVER(HAS_TRIBE(Tribe.LOST_SOUL), ~HAS_TRIBE(Tribe.ALL), n=2)
        ).to(
            CHOICE_SELECTED.buff(cost=+1, attack=+1, hp=+1)
            >> CHOICE_SELECTED.add_keyword(HASTE)
            >> CHOICE_SELECTED.to_hand()
        )
    )


@card(479)
class Fly(Monster):
    magic = SELF.schedule_delay_effect()

    delay = SELF.force_attack(FRONT(SELF))


@card(493)
class SnailBucket(Monster):
    red_snail: Var[Card] = Var(Card)
    yellow_snail: Var[Card] = Var(Card)

    dust = (
        SetVar(var=red_snail, value=GENERATE_CARD("Red Snail"))
        >> red_snail.summon()
        >> SetVar(var=yellow_snail, value=GENERATE_CARD("Yellow Snail"))
        >> yellow_snail.summon()
        >> ((red_snail | yellow_snail) >> RANDOM(1)).trigger_ability(MAGIC)
    )


@card(495)
class CrossBomb(Monster):
    front_monster: Var[TargetSelector] = Var(TargetSelector)
    hit_result: Var[StepResult] = Var(StepResult)

    turn_start = (
        SetVar(var=front_monster, value=FRONT(SELF))
        >> Check(front_monster).to(
            SELF.kill().to(
                front_monster.hit(5).store_result(hit_result).to(
                    OPPONENT.hit(hit_result.excess_damage)
                )
            )
        )
    )


@card(499)
class AnimeSword(Monster):
    magic = SELF.schedule_delay_effect()

    delay = ((HAND & IS_MONSTER) >> RANDOM(1)).buff(
        attack=SELF.attack,
        hp=SELF.max_hp
    )


@card(509)
class LongSink(Monster):
    turn_end = Check(~SELF.has_attacked).to(YOU.heal(3))


@card(512)
class GameBomb(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        return GENERATE_CARD("Dynamite Stick").summon()


@card(523)
class SnoringMonsters(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.hit(4)

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.killer_id != self.id:
            return None

        return SELF.buff(attack=+3)


@card(534)
class Carbed(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="+3 ATK while damaged",
            applies=lambda q: (q.monster is self) and (self.hp_missing > 0),
            apply=lambda attack, q: attack + 3,
        )


@card(539)
class BoneDrawer(Monster):
    dust = GENERATE_CARD("Pile of Bones").to_hand()


@card(541)
class Painting(Monster):
    targets = ALLY_MONSTERS & (TEMPLATE_ID != SELF.template_id) & (RARITY <= EPIC)

    magic = (
        (TARGET >> COPY()).to_deck()
        >> SELF.schedule_delay_effect()
    )

    delay = YOU.draw_next()


@card(542)
class TrashBall(Monster):
    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        card_ = game.entity(res.card_id)
        if not isinstance(card_, Monster):
            return None

        return card_.actions.hit(1)


@card(557)
class MadDragon(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        if game.turn_player.id != self.controller_id:
            return None

        return (
            SELF.set_status(DODGE, value=SELF.status(DODGE) + 1)
            >> SELF.add_keyword(HASTE)
            >> SELF.refresh_attacks()
        )


@card(559)
class LaggyTV(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        def applies(q: CostQuery) -> bool:
            return (
                q.card.zone is CardZone.HAND
                and isinstance(q.card, Monster)
                and q.card.controller_id == self.controller_id
            )

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="Monsters in your hand have +1 COST",
            applies=applies,
            apply=lambda cost, q: cost + 1,
        )

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if not res.is_played:
            return None

        monster = game.entity(res.monster_id)
        if monster.controller_id != self.controller_id:
            return None

        return monster.actions.buff(attack=+1, hp=+2)


@card(560)
class MomSlime(Monster):
    @on_event(GoldSpentResult)
    def on_gold_spent(self, res: GoldSpentResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.reason != 'play_spell':
            return None

        return GENERATE_CARD("Kid Slime").summon()


@card(562)
class OverlordMigosp(Monster):
    def dust(self, ctx, **kwargs):
        if ctx.game.turn_player.id == self.controller_id:
            return None

        return GENERATE_CARD("Migosp").summon()


@card(563)
class IcedButterfly(Monster):
    magic = GENERATE_CARD("Iced Butterfly").summon()


@card(566)
class FoxBodyguard(Monster):
    summon_result: Var[StepResult] = Var(StepResult)

    dust = GENERATE_CARD("Fox Head").summon().store_result(summon_result).to(
        TriggerAbility(target=summon_result.monster_id, ability=MAGIC)
    )


@card(587)
class GlowingShroom(Monster):
    magic = Switch(
        left=SELF.swap_stats(),
        right=NO_EFFECT
    )

    @on_event(GoldSpentResult)
    def on_gold_spent(self, res: GoldSpentResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.reason != 'play_spell':
            return None

        return SELF.buff(attack=+1)


@card(589)
class TheMascot(Monster):
    shock = GENERATE_CARD("Draft").to_hand()


@card(591)
class MemoryKeeper(Monster):
    targets = ALL_MONSTERS

    magic = (
        TARGET.set_stats(hp=2)
        >> TARGET.set_status(DODGE, value=1)
    )

    shock = (ENEMY_MONSTERS >> MAX(HP)).hit(2)


@card(599)
class Stalagmite(Monster):
    _effect = GENERATE_CARD("Gemstone").to_hand()

    magic = _effect
    dust = _effect

    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="Enemy monsters take +2 DMG from Gemstones",
            applies=lambda q: (
                isinstance(q.target, Monster)
                and q.target.controller_id != self.controller_id
                and isinstance(q.source, Card)
                and q.source.template.id == 598
            ),
            apply=lambda damage, q: damage + 2,
        )


@card(604)
class WaterfallSign(Monster):
    dust = GENERATE_CARD("Gemstone").to_hand() * 2

    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.template.id != 598:
            return None

        if res.card.creator_base_identity == self.base_identity:
            return None

        return GENERATE_CARD("Gemstone").to_hand()


@card(606)
class LibrarbySign(Monster):
    magic = (
        YOU.draw((DECK & (RARITY == COMMON)).first())
        >> YOU.draw((DECK & (RARITY == RARE)).first())
        >> YOU.draw((DECK & (RARITY == EPIC)).first())
    )


@card(611)
class DogTreats(Monster):
    dust = (ALLY_MONSTERS & HAS_TRIBE(Tribe.DOG)).buff(attack=+1, hp=+1)


@card(805)
class Yandereplane(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(~SELF.has_attacked).to(
        SELF.kill().to(
            ENEMIES.hit(3)
        )
    )


@card(951)
class FireFountain(Monster):
    dust = DEATH_SLOT.enchant(
        ENCHANTMENT_BY_NAME('the-flame')
    )
