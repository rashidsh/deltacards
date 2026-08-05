from deltacards.dsl.api import *


@card(240)
class TV(Monster):
    random_template: Var[TargetSelector] = Var(TargetSelector)
    your_card: Var[Card] = Var(Card)
    enemy_card: Var[Card] = Var(Card)

    turbo = (
        SetVar(
            var=random_template,
            value=(CARD_LIBRARY & NON_TOKEN) >> RANDOM(1),
        )
        >> SetVar(
            var=your_card,
            value=random_template >> GENERATE_CARD(),
        )
        >> your_card.buff(cost=-1)
        >> your_card.to_deck(pos='top')
        >> SetVar(
            var=enemy_card,
            value=random_template >> GENERATE_CARD(controller=OPPONENT),
        )
        >> enemy_card.to_deck(controller=OPPONENT, pos='top')
    )


@card(274)
class Starwalker(Monster):
    need = ~EXISTS(
        DECK
        & NON_GENERATED
        & ((RARITY == RARE) | (RARITY == EPIC))
    )

    targets = HAND

    magic = (
        TARGET.buff(cost=-4)
        >> TARGET.to_deck()
    )


@card(294)
class Rudinn(Monster):
    magic = YOU.choose(
        DISCOVER(
            IS_MONSTER,
            EXPANSION(Expansion.DELTARUNE),
            COST >= 2,
            COST <= 4,
            n=3,
        )
    ).to(
        CHOICE_SELECTED.buff(attack=+1)
        >> CHOICE_SELECTED.to_hand()
    )


@card(295)
class Jigsawry(Monster):
    magic = Check(
        COUNT(ALLY_MONSTERS & (TEMPLATE_ID == SELF.template_id)) >= 4
    ).to(
        (ALLY_MONSTERS & (TEMPLATE_ID == SELF.template_id)).set_status(DODGE, value=1)
        >> (ALLY_MONSTERS & (TEMPLATE_ID == SELF.template_id)).add_keyword(TAUNT)
        >> (ALLY_MONSTERS & (TEMPLATE_ID == SELF.template_id)).add_keyword(CHARGE)
    )


@card(296)
class JarOfWorms(Monster):
    magic = (
        GENERATE_CARD("Worm").summon()
        >> Check(SPENT_GOLD_ON_SPELLS_LAST_TURN).to(
            GENERATE_CARD("Worm").summon()
        )
    )


@card(297)
class StarwalkerBird(Monster):
    need = ~EXISTS(
        DECK
        & NON_GENERATED
        & ((RARITY == RARE) | (RARITY == EPIC))
    )

    magic = YOU.draw_next() * 3


@card(298)
class Rabbick(Monster):
    turbo = GENERATE_CARD("Clean Rabbick").to_hand()
    dust = GENERATE_CARD("Clean Rabbick").summon()


@card(299)
class PoliticianBear(Monster):
    targets = ALLY_MONSTERS

    magic = FRONT(TARGET).hit(TARGET.attack)


@card(301)
class ToyBlock(Monster):
    turn_start = SELF.swap_stats()
    turn_end = SELF.swap_stats()


@card(306)
class SmolderCake(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.add_keyword(CANDY)


@card(309)
class LancerPainting(Monster):
    dust = GENERATE_CARD("Spade").to_hand()


@card(310)
class GreenFire(Monster):
    magic = (
        ADJACENT(SELF).hit(2)
        >> FRONT(SELF).hit(2)
    )


@card(311)
class Chest(Monster):
    dust = YOU.draw_next() * 2


@card(314)
class FanRudinn(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.buff(attack=+1, hp=+2)


@card(373)
class Worm(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.source_id != self.id:
            return None

        target = game.entity(res.target_id)
        if not isinstance(target, Monster):
            return None

        return YOU.heal(res.amount)


@card(389)
class Mirror(Monster):
    released_card: Var[Card] = Var(Card)

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.set_base_stats(
            cost=SELF.base.cost,
            attack=SELF.base.attack,
            hp=SELF.base.hp
        )
        >> released_card.summon(controller=YOU)
    )

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return SELF.catch(res.defender_id)


@card(390)
class BallPerson(Monster):
    magic = (ALLY_MONSTERS & ~SELF).silence()


@card(393)
class CoatRack(Monster):
    monster: Var[Card] = Var(Card)

    magic = (
        For(
            2,
            (
                SetVar(var=monster, value=(DECK & IS_MONSTER).first())
                >> YOU.draw(monster).to(
                    monster.buff(cost=+1, attack=+1, hp=+2)
                )
            )
        )
    )


@card(407)
class CashRegister(Monster):
    targets = HAND & IS_MONSTER & HAS_ABILITY(TURBO)

    magic = (
        TARGET.trigger_ability(TURBO)
        >> Check(SELF.pos <= 1).to(
            TARGET.to_deck().to(
                YOU.draw_next()
            )
        )
    )


@card(421)
class AsgoresTruck(Monster):
    magic = GENERATE_CARD("Red Flower").to_hand() * 2


@card(436)
class TownHallGuy(Monster):
    targets = HAND & IS_MONSTER & HAS_KEYWORD(HASTE)

    magic = TARGET.buff(attack=+1)


@card(450)
class DeskLamp(Monster):
    dust = GENERATE_CARD("Dream").to_hand()


@card(490)
class PileOfDust(Monster):
    dust = Check(KILLER & IS_MONSTER).to(
        KILLER.buff(attack=+2, hp=+2)
    )

    turn_end = SELF.kill()


@card(500)
class IceEMascot(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id == self.controller_id:
            return None

        return (
            Paralyze(target=res.monster_id)
            >> Buff(target=res.monster_id, attack=-1)
            >> SELF.silence()
        )


@card(538)
class WobblyThing(Monster):
    support = SELF.kill().to(
        ((HAND & IS_MONSTER) >> RANDOM(2)).buff(attack=+1, hp=+1)
    )


@card(546)
class Sadmobile(Monster):
    draw_result: Var[StepResult] = Var(StepResult)

    magic = YOU.draw_next().store_result(draw_result).to(
        Check(SPENT_GOLD_LAST_TURN >= 7).to(
            Buff(target=draw_result.card_id, cost=-2)
        )
    )


@card(567)
class BlowingRabbick(Monster):
    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.cost < 1:
            return None

        attack_buff = self.buffs.attack
        hp_buff = self.buffs.max_hp

        return SELF.to_hand().to(
            SELF.buff(attack=attack_buff + 1, hp=hp_buff + 1)
        )


@card(582)
class TinyBookshelf(Monster):
    need = SPENT_GOLD_ON_SPELLS_LAST_TURN

    magic = (
        SELF.buff(attack=+1)
        >> SELF.add_keyword(TAUNT)
    )


@card(600)
class BagOGoodies(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        DISCOVER(
            IS_SPELL,
            NON_TOKEN,
            COST >= 2,
            n=3,
        )
    ).to(
        CHOICE_SELECTED.buff(
            cost=-COUNT(
                SPELLS_CAST(player=YOU, scope=THIS_TURN)
                & (TEMPLATE_NAME == "Gemstone")
            )
        )
        >> CHOICE_SELECTED.to_hand()
    )

    shock = (
        SetVar(var=generated_card, value=GENERATE_CARD("Gemstone"))
        >> generated_card.set_stats(cost=0)
        >> generated_card.to_hand()
    )


@card(618)
class CheeseBlock(Monster):
    copied_card: Var[Card] = Var(Card)

    dust = (
        SetVar(
            var=copied_card,
            value=(
                DECK
                & IS_MONSTER
                & (COST <= 1)
                & (TEMPLATE_ID != SELF.template_id)
            ) >> RANDOM(1) >> COPY()
        )
        >> copied_card.set_base_stats(attack=1, hp=1)
        >> copied_card.summon()
    )


@card(619)
class MausHole(Monster):
    magic = YOU.choose(
        DISCOVER(
            NON_DT,
            NON_TOKEN,
            COST == 1,
            n=3,
        )
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(620)
class Rotablock(Monster):
    copied_card: Var[Card] = Var(Card)

    magic = For(
        3,
        (
            SetVar(
                var=copied_card,
                value=(
                    DUSTPILE
                    & IS_MONSTER
                    & NON_DT
                    & (COST <= 1)
                ) >> RANDOM(1) >> COPY()
            )
            >> copied_card.to_deck()
        )
    )


@card(625)
class StuckTasque(Monster):
    targets = HAND

    magic = (TARGET | LEFT_IN_HAND(TARGET)).buff(cost=-1)


@card(628)
class YarnBall(Monster):
    magic = (
        HAND.bottom(2).to_deck()
        >> (YOU.draw_next() * 3)
    )


@card(629)
class TasquePainting(Monster):
    magic = LOOP_COPY.buff(
        cost=-COUNT(
            CARDS_PLAYED(player=YOU, scope=THIS_TURN)
            & (BASE_COST >= 1)
            & (TEMPLATE_ID != SELF.template_id)
        )
    )


@card(633)
class WigPerson(Monster):
    targets = ALLY_MONSTERS

    magic = (
        TARGET.swap_stats()
        >> TARGET.silence()
    )


@card(636)
class Dumpster(Monster):
    magic = YOU.draw((DECK & (RARITY == BASE)).first())


@card(637)
class CafeJukebox(Monster):
    magic = YOU.choose(
        (
            OPPONENT_DUSTPILE
            & IS_MONSTER
            & NON_DT
        ) >> RANDOM(3) >> COPY()
    ).to(
        CHOICE_SELECTED.buff(attack=+1, hp=+1)
        >> CHOICE_SELECTED.to_deck()
    )


@card(638)
class DogCone(Monster):
    targets = ALL_PLAYERS | ALL_MONSTERS

    magic = TARGET.heal(2)


@card(640)
class AestheticAaron(Monster):
    targets = HAND
    magic = TARGET.to_hand(controller=OPPONENT).to(
        YOU.draw_next()
    )


@card(641)
class CafeTable(Monster):
    targets = ALLY_MONSTERS

    magic = (
        TARGET.remove_negative_effects()
        >> TARGET.add_keyword(TAUNT)
    )


@card(651)
class TrafficCar(Monster):
    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.killer_id != self.id:
            return None

        return ENEMY_MONSTERS.hit(1)


@card(658)
class CyberBalloon(Monster):
    magic = YOU.earn_gold(COUNT(ALLY_MONSTERS & GENERATED))


@card(659)
class CyberTrash(Monster):
    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = Check(DUSTPILE & IS_MONSTER & (RARITY == BASE)).to(
        Program(1).to(
            SetVar(
                var=copied_cards,
                value=(
                    DUSTPILE
                    & IS_MONSTER
                    & (RARITY == BASE)
                ) >> RANDOM(2) >> COPY()
            )
            >> copied_cards.buff(cost=-1)
            >> copied_cards.to_hand()
        )
    )


@card(660)
class CyberTree(Monster):
    magic = SELF.schedule_delay_effect()

    delay = (
        (ALLY_MONSTERS & GENERATED & ~SELF).buff(attack=+1, hp=+1)
        >> Program(1).to(
            (ALLY_MONSTERS & GENERATED & ~SELF).buff(attack=+1, hp=+1)
        )
    )


@card(662)
class EggplantTrashbag(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        DISCOVER(
            IS_SPELL,
            (RARITY == BASE),
            n=4
        )
    ).to(
        SetVar(var=generated_card, value=CHOICE_SELECTED)
        >> SELF.schedule_delay_effect()
    )

    delay = generated_card.to_hand()


@card(663)
class SadBunbun(Monster):
    magic = YOU.choose(
        DUSTPILE
        & IS_MONSTER
        & (COST == 0)
    ).to(
        (CHOICE_SELECTED >> COPY()).summon().to(
            SELF.buff(attack=+2)
            >> CHOICE_SELECTED.erase()
        )
    )


@card(667)
class TinyTornado(Monster):
    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return GENERATE_CARD("Zephyr").to_hand()


@card(669)
class Stickman(Monster):
    targets = ENEMY_MONSTERS

    magic = (
        TARGET.buff(attack=-3)
        >> SELF.schedule_delay_effect()
    )

    delay = Check(TARGET.dead).to(
        GENERATE_CARD("Dancing Stickman").to_hand()
    )


@card(676)
class MilkLooker(Monster):
    @on_event(DodgeConsumedResult)
    def on_dodge_consumed(self, res: DodgeConsumedResult, game, **kwargs):
        if res.monster.id != self.id:
            return None

        return GENERATE_CARD("Sans Milk").to_hand()


@card(678)
class Cauldron(Monster):
    generated_card: Var[Card] = Var(Card)

    shock = (
        SetVar(var=generated_card, value=GENERATE_CARD("Spincake"))
        >> generated_card.set_base_stats(cost=1, attack=1, hp=1)
        >> generated_card.add_keyword(HASTE)
        >> generated_card.buff(
            cost=TRIGGER_CARD.cost // 2,
            attack=TRIGGER_CARD.cost // 2,
            hp=TRIGGER_CARD.cost // 2,
        )
        >> generated_card.to_hand()
    )


@card(729)
class BookRegister(Monster):
    targets = ALL_MONSTERS

    magic = Check(
        HAND
        & IS_SPELL
        & NON_TOKEN
        & (CARD_SOUL != None)
        & (CARD_SOUL != PLAYER_SOUL(player=YOU))
    ).to(
        TARGET.hit(3)
    )


@card(752)
class LancersBikeBed(Monster):
    @on_event(CardDrawnResult)
    def on_card_drawn(self, res: CardDrawnResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        drawn_card = game.entity(res.card_id)
        if not isinstance(drawn_card, Monster):
            return None

        return drawn_card.actions.buff(attack=+1)


@card(754)
class FlyingHeads(Monster):
    dust = GENERATE_CARD(
        "Hyperlink Blocked",
        controller=OPPONENT
    ).to_deck(controller=OPPONENT) * 3


@card(755)
class SpamtonPoster(Monster):
    magic = YOU.draw((DECK & IS_SPELL).first())

    shock = For(
        TRIGGER_CARD.cost,
        GENERATE_CARD(
            "Hyperlink Blocked",
            controller=OPPONENT
        ).to_deck(controller=OPPONENT)
    )


@card(756)
class SpamtonShop(Monster):
    turn_end = Program(3).to(
        GENERATE_CARD("Pipis").summon() * 2
    )


@card(765)
class TrashRudinn(Monster):
    generated_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=generated_cards,
            value=(
                CARD_LIBRARY
                & IS_MONSTER
                & (RARITY == BASE)
                & EXPANSION(Expansion.DELTARUNE)
            ) >> SORT_BY(COST) >> GENERATE_CARD()
        )
        >> generated_cards.to_hand()
        >> SELF.schedule_delay_effect()
    )

    delay = (generated_cards & HAND).erase()


@card(786)
class DustyChest(Monster):
    erased_count: Var[int] = Var(int)

    magic = (
        SetVar(var=erased_count, value=COUNT((DUSTPILE & IS_MONSTER)[:9]))
        >> (DUSTPILE & IS_MONSTER)[:9].erase()
        >> For(erased_count // 3, YOU.draw_next())
    )


@card(881)
class Cuptain(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="Cuptains in your hand have +1 COST.",
            applies=lambda q: q.card.template_id == self.template_id,
            apply=lambda cost, q: cost + 1,
        )

        other_cuptains = sum(
            1
            for card_ in game.player(self.controller_id).board.cards
            if (
                card_ is not self
                and card_.template is self.template
            )
        )

        if other_cuptains <= 0:
            return

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="+1 ATK for each other ally Cuptain",
            applies=lambda q: q.monster is self,
            apply=lambda attack, q: attack + other_cuptains,
        )

        yield IntModifier(
            kind=ModKind.MAX_HP,
            layer=StatLayer.ADD,
            source=self,
            description="+1 HP for each other ally Cuptain",
            applies=lambda q: q.monster is self,
            apply=lambda max_hp, q: max_hp + other_cuptains,
        )


@card(895)
class Organikk(Monster):
    support = SELF.set_stats(attack=ATTACKER.attack)


@card(896)
class Longanikk(Monster):
    support = SELF.set_stats(hp=ATTACKER.hp)


@card(902)
class Shadowguy(Monster):
    targets = ALL_MONSTERS

    monsters_in_hand: Var[TargetSelector] = Var(TargetSelector)

    magic = Check(TARGET & HAS_KEYWORD(WANTED)).to(
        (
            SetVar(var=monsters_in_hand, value=((OPPONENT_HAND & IS_MONSTER) >> RANDOM(3)))
            >> monsters_in_hand.reveal()
            >> monsters_in_hand.add_keyword(WANTED)
        ),
        else_=TARGET.add_keyword(WANTED)
    )


@card(905)
class Lawnmower(Monster):
    dust = (
        (ALLY_MONSTERS & ~SELF).buff(attack=+1)
        >> (ALLY_MONSTERS & ~SELF).add_keyword(HASTE)
    )


@card(911)
class Crossganikk(Monster):
    need = SPENT_GOLD_ON_SPELLS_LAST_TURN

    magic = GENERATE_CARD("Dream").to_hand() * 2


@card(924)
class Mizzle(Monster):
    healed_monster: Var[TargetSelector] = Var(TargetSelector)

    turn_end = Check(ALLY_MONSTERS & DAMAGED).to(
        SetVar(
            var=healed_monster,
            value=(ALLY_MONSTERS & DAMAGED) >> MIN(HP),
        )
        >> healed_monster.heal(2)
        >> Check(healed_monster.hp == healed_monster.max_hp).to(
            SELF.buff(attack=+1, hp=+1)
        )
    )


@card(932)
class PixelVase(Monster):
    targets = ENEMY_MONSTERS

    magic = TARGET.buff(attack=-1, hp=-1)


@card(956)
class TuningFork(Monster):
    delay = Check(SELF.hp == COUNT(HAND)).to(
        SELF.buff(attack=+1, hp=+1)
        >> (YOU.draw_next() * 2)
    )


@card(957)
class PixelLizard(Monster):
    turn_end = Check(
        GOLD_SPENT(player=YOU, scope=THIS_TURN)
        & TOKEN
        & (TEMPLATE_NAME != "Lightning Bolt")
    ).to(
        GENERATE_CARD("Lightning Bolt").to_hand()
    )


@card(961)
class Shi(Monster):
    turn_start = Switch(
        left=(ALLY_MONSTERS & ~SELF).buff(attack=+1, hp=+1),
        right=ENEMIES.hit(1)
    )


@card(963)
class Strengthmeter(Monster):
    magic = SELF.buff(
        attack=SUM(ADJACENT(SELF), ATTACK)
    )


@card(964)
class MantisDancer(Monster):
    targets = ALL_PLAYERS | ALL_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)

    magic = (
        TARGET.hit(3).store_result(hit_result).to(
            Check(hit_result.killed).to(
                Cast(
                    card=GENERATE_CARD("Carousel"),
                    controller=YOU
                )
            )
        )
    )


@card(967)
class Floradinn(Monster):
    turn_start = GENERATE_CARD("Green Clover").to_hand() * 2


@card(968)
class CherryTree(Monster):
    turn_start = SELF.buff(hp=+2)


@card(972)
class Terakota(Monster):
    targets = ALLY_SLOTS

    magic = TARGET.enchant(
        ENCHANTMENT_BY_NAME('soil')
    )


@card(976)
class Leafling(Monster):
    generated_cards: Var[TargetSelector] = Var(TargetSelector)
    generated_card: Var[TargetSelector] = Var(TargetSelector)

    support = Check(
        ATTACKER & (TEMPLATE_NAME != "Green Clover")
    ).to(
        SetVar(
            var=generated_cards,
            value=GENERATE_CARD(
                "Green Clover",
                count=EMPTY_SLOTS(BOARD)
            )
        )
        >> generated_cards.summon()
        >> ForEach(
            generated_cards,
            var=generated_card,
            effect=generated_card.force_attack(DEFENDER)
        )
    )


@card(984)
class TerakotaArcher(Monster):
    targets = ENEMY_MONSTERS

    magic = TARGET.hit(COUNT(HAND))
    bullseye = GENERATE_CARD("Green Clover").summon(attack=2, hp=3)
