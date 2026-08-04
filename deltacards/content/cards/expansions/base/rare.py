from deltacards.dsl.api import *


@card(12)
class Chilldrake(Monster):
    magic = Switch(
        left=YOU.draw((DECK & IS_MONSTER).first()),
        right=YOU.draw((DECK & IS_SPELL).first())
    )


@card(30)
class Burgerpants(Monster):
    turn_end = ALL_PLAYERS.earn_gold(5)


@card(42)
class SoSorry(Monster):
    magic = GENERATE_CARD("Doodlebog").to_hand()


@card(49)
class Glyde(Monster):
    magic = SELF.buff(
        attack=COUNT(HAND),
        hp=COUNT(HAND)
    )


@card(51)
class MonsterKid(Monster):
    dust = (ALLY_MONSTERS & ~SELF).buff(attack=+1, hp=+1)


@card(101)
class NacaratJester(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.silence()


@card(111)
class MemorialStatue(Monster):
    magic = Check(COUNT(ALLY_MONSTERS) <= COUNT(ENEMY_MONSTERS)).to(
        SELF.add_keyword(HASTE)
    )

    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return defender.actions.silence()


@card(112)
class IceWolf(Monster):
    dust = GENERATE_CARD("Ice", controller=OPPONENT).summon(controller=OPPONENT)


@card(114)
class GladDummy(Monster):
    magic = ADJACENT(SELF).add_keyword(TAUNT)


@card(126)
class PapyrusStatue(Monster):
    magic = Check(COUNT(HAND) >= 5).to(
        SELF.add_keyword(TAUNT)
    )


@card(127)
class Garbage(Monster):
    _effect = (
        (
            CARD_LIBRARY
            & IS_SPELL
            & (RARITY == BASE)
            & (CARD_SOUL == PLAYER_SOUL(player=YOU))
        ).first()
        >> GENERATE_CARD()
    ).to_hand()

    magic = _effect
    dust = _effect


@card(135)
class BigMouth(Monster):
    _effect = ((ENEMY_MONSTERS & (COST <= 2)) >> RANDOM(1)).kill().to(
        YOU.heal(2)
    )

    magic = _effect
    turn_start = _effect


@card(137)
class BigBob(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        if game.turn_player.id != self.controller_id:
            return None

        if res.killed:
            return None

        return GENERATE_CARD("Big Bob").summon()


@card(145)
class DiamondBoy1(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        def applies(q: DamageQuery) -> bool:
            return (
                q.target is not self
                and isinstance(q.target, Monster)
                and q.target.controller_id == self.controller_id
                and not q.target.has_keyword(CardKeyword.ARMOR)
            )

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="Other non-Armor ally monsters take 1 less DMG (can't stack)",
            applies=applies,
            apply=lambda damage, q: damage - 1,
            unique=True,
            key="non_armor_allies:-1_damage",
        )


@card(146)
class DiamondBoy2(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        opponent = game.player(self.controller_id).opponent

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="The opponent takes 2 less DMG.",
            applies=lambda q: q.target is opponent,
            apply=lambda damage, q: damage - 2,
        )


@card(149)
class DogHouse(Monster):
    targets = HAND & HAS_TRIBE(Tribe.DOG)

    magic = (TARGET >> EXACT_COPY()).to_deck(pos='top')


@card(150)
class NiceCreamGuy(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        return Buff(target=res.monster_id, attack=+1, hp=+1)


@card(151)
class EchoFish(Monster):
    targets = ENEMY_MONSTERS

    magic = (
        SELF.set_stats(attack=TARGET.attack, hp=TARGET.hp)
        >> Check(TARGET & HAS_KEYWORD(TAUNT)).to(
            SELF.add_keyword(TAUNT)
        )
        >> Check(TARGET & HAS_KEYWORD(CANDY)).to(
            SELF.add_keyword(CANDY)
        )
        >> Check(TARGET & HAS_KEYWORD(CHARGE)).to(
            SELF.add_keyword(CHARGE)
        )
        >> Check(TARGET & HAS_KEYWORD(HASTE)).to(
            SELF.add_keyword(HASTE)
        )
        >> Check(TARGET & HAS_KEYWORD(DARKSPAWN)).to(
            SELF.add_keyword(DARKSPAWN)
        )
        >> Check(TARGET & HAS_STATUS(DODGE)).to(
            SELF.set_status(DODGE, value=TARGET.status(DODGE))
        )
        >> Check(TARGET & HAS_KEYWORD(TRANSPARENCY)).to(
            SELF.add_keyword(TRANSPARENCY)
        )
    )


@card(160)
class SnowPoff(Monster):
    magic = SELF.schedule_delay_effect()

    delay = YOU.draw((DECK & HAS_TRIBE(Tribe.DOG)).first())

    dust = YOU.draw_next()


@card(161)
class ClamGirl(Monster):
    magic = ((HAND & IS_SPELL) >> RANDOM(2)).buff(cost=-2)


@card(162)
class ClamBoy(Monster):
    generated_card: Var[Card] = Var(Card)

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return (
            SetVar(var=self.generated_card, value=DISCOVER(NON_TOKEN, COST == 2))
            >> self.generated_card.buff(cost=-1)
            >> self.generated_card.to_hand()
        )


@card(171)
class DimensionalBox(Monster):
    targets = ENEMY_MONSTERS

    released_card: Var[Card] = Var(Card)

    magic = SELF.catch(TARGET)

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.summon(controller=released_card.controller)
    )


@card(173)
class TemmieStatue(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_tribe(Tribe.TEMMIE):
            return None

        return Buff(target=res.monster_id, attack=+1, hp=+1)


@card(174)
class Receptionist2(Monster):
    magic = SELF.buff(hp=COUNT(ENEMY_MONSTERS))


@card(185)
class Librarian(Monster):
    generated_cards: Var[TargetSelector] = Var(TargetSelector)

    need = (
        COUNT(DECK & NON_GENERATED)
        == COUNT_DISTINCT(DECK & NON_GENERATED, TEMPLATE_ID)
    )

    magic = (
        (YOU.draw_next() * 3)
        >> SetVar(
            var=generated_cards,
            value=(CARD_LIBRARY & NON_TOKEN) >> RANDOM(3) >> GENERATE_CARD(),
        )
        >> generated_cards.buff(cost=-1)
        >> generated_cards.to_deck()
    )


@card(186)
class TrashTornado(Monster):
    magic = SELF.schedule_delay_effect()

    delay = (
        LOOP_COPY.buff(attack=+1, hp=+1)
        >> LOOP_COPY.to_deck()
    )


@card(191)
class VulkinsCloud(Monster):
    turn_start = (ENEMY_MONSTERS >> RANDOM(1)).hit(SELF.attack)


@card(193)
class DiscoBall(Monster):
    X: Var[Card] = Var(Card)
    generated_card: Var[Card] = Var(Card)

    magic = ForEach(
        HAND & IS_SPELL,
        var=X,
        effect=(
            SetVar(
                var=generated_card,
                value=(
                    CARD_LIBRARY
                    & IS_SPELL
                    & NON_TOKEN
                    & (TEMPLATE_ID != X.template_id)
                ) >> RANDOM(1) >> GENERATE_CARD()
            )
            >> Check(generated_card).to(
                X.turn_into(generated_card)
                >> generated_card.buff(cost=-1)
            )
        )
    )


@card(197)
class ElderPuzzler(Monster):
    turn_end = Check(~SELF.has_attacked).to(
        (ENEMY_MONSTERS >> RANDOM(1)).hit(4)
    )


@card(198)
class RedBird(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.turn_into(
        (
            CARD_LIBRARY
            & IS_MONSTER
            & NON_TOKEN
            & (COST == TARGET.cost)
            & (TEMPLATE_ID != TARGET.template_id)
        )
        >> RANDOM(1)
        >> GENERATE_CARD()
    )


@card(199)
class Manticore(Monster):
    magic = (
        (YOU.draw_next() * 2)
        >> (OPPONENT.draw_next() * 2)
    )


@card(215)
class Coffin(Monster):
    released_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (
            DUSTPILE
            & (TEMPLATE_ID != SELF.template_id)
        ) >> MIN(COST, n=2)
    ).to(
        SELF.catch(CHOICE_SELECTED)
    )

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.summon(controller=released_card.controller)
    )


@card(216)
class FireTrap(Monster):
    turn_end = OPPONENT.hit(SELF.age)


@card(220)
class Timer(Monster):
    turn_start = Check(
        (SELF.age > 0) & (SELF.age % 3 == 0)
    ).to(
        SkipNextTurn(player=OPPONENT)
    )


@card(221)
class SkateboardGirl(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(SELF & BOARD).to(
        Check(SELF.has_attacked).to(
            SELF.to_hand()
        )
    )


@card(227)
class CoffeeMan(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.silence()


@card(237)
class PunkHamster(Monster):
    turbo = Check(SELF & GENERATED).to(
        YOU.hit(4)
    )

    dust = GENERATE_CARD("Punk Hamster", controller=OPPONENT).to_deck(controller=OPPONENT)


@card(239)
class SnowdinSign(Monster):
    need = SPENT_GOLD_ON_SPELLS_LAST_TURN

    magic = YOU.choose(
        DISCOVER(IS_SPELL, RARITY == RARE, n=3)
    ).to(
        CHOICE_SELECTED.buff(cost=-1)
        >> CHOICE_SELECTED.to_hand()
    )


@card(245)
class Editor1(Monster):
    magic = YOU.choose(
        DECK & IS_MONSTER & HAS_ABILITY(TURBO)
    ).to(
        CHOICE_SELECTED.buff(cost=-1)
        >> CHOICE_SELECTED.to_deck(pos='top')
    )


@card(246)
class Editor2(Monster):
    magic = YOU.choose(
        DISCOVER(IS_MONSTER, NON_TOKEN, n=5)
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(248)
class BusinessDude(Monster):
    gold_spent_result: Var[StepResult] = Var(StepResult)

    turn_end = (
        Check(YOU.gold > 0).to(
            YOU.spend_gold(YOU.gold).store_result(gold_spent_result).to(
                SELF.buff(attack=gold_spent_result.amount, hp=gold_spent_result.amount)
            )
        )
    )


@card(408)
class SpaceCooler(Monster):
    _effect = ((HAND & IS_MONSTER) >> RANDOM(1)).buff(attack=+1, hp=+1)

    magic = SELF.schedule_delay_effect()

    delay = _effect
    turn_end = _effect


@card(409)
class ActionFigures(Monster):
    targets = ALLY_MONSTERS & NON_DT

    copied_card: Var[Card] = Var(Card)

    magic = (
        TARGET.silence()
        >> SetVar(var=copied_card, value=TARGET >> COPY())
        >> copied_card.add_keyword(SILENCED)
        >> copied_card.to_hand()
    )


@card(432)
class Popumeter(Monster):
    support = SELF.force_attack(ENEMY_MONSTERS >> RIGHTMOST)


@card(439)
class Candle(Monster):
    copied_card: Var[Card] = Var(Card)

    dust = (
        SetVar(var=copied_card, value=SELF >> COPY())
        >> copied_card.set_base_stats(hp=1)
        >> copied_card.add_keyword(SILENCED)
        >> copied_card.summon()
    )


@card(440)
class CrystalCheese(Monster):
    released_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (CARD_LIBRARY & HAS_TRIBE(Tribe.LOST_SOUL))
        >> RANDOM(2)
        >> GENERATE_CARD()
    ).to(
        SELF.catch(CHOICE_SELECTED)
    )

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.set_stats(attack=1, hp=1)
        >> released_card.summon(controller=released_card.controller)
    )


@card(497)
class FireChimney(Monster):
    magic = Check(
        CARDS_PLAYED(player=YOU, scope=THIS_TURN) & (BASE_COST >= 6)
    ).to(
        SELF.buff(attack=+1, hp=+1)
        >> SELF.add_keyword(HASTE)
    )


@card(498)
class SnailPen(Monster):
    magic = (
        (ALLY_MONSTERS & HAS_TRIBE(Tribe.SNAIL))
        >> EXACT_COPY()
    ).to_hand()


@card(501)
class CoolBone(Monster):
    def magic(self, ctx, **kwargs):
        effect = NO_EFFECT

        for monster in ctx.game.player(self.controller_id).board.cards:
            if not monster.has_tribe(Tribe.DOG):
                continue

            keyword_or_status = ctx.game.rng.choice((TAUNT, CANDY, ARMOR, 'dodge'))

            if keyword_or_status == 'dodge':
                effect = effect >> (
                    monster.actions.set_status(
                        DODGE,
                        value=monster.get_status(DODGE) + 1
                    )
                )

            else:
                effect = effect >> monster.actions.add_keyword(keyword_or_status)

        return effect


@card(507)
class Fireplace(Monster):
    shock = SELF.heal(3)


@card(510)
class CrackedTable(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Tea Set"))
        >> Check(YOU.hp < OPPONENT.hp).to(
            generated_card.buff(cost=-1)
        )
        >> generated_card.to_hand()
    )


@card(521)
class Pillar(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.buff(attack=+2, hp=+1)

    dust = GENERATE_CARD("Broken Pillar").to_hand()


@card(532)
class EasyToDrawBed(Monster):
    generated_card: Var[Card] = Var(Card)

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if res.attacker_dead:
            return None

        return (
            SetVar(
                var=self.generated_card,
                value=(CARD_LIBRARY & IS_MONSTER & NON_TOKEN) >> RANDOM(1) >> GENERATE_CARD()
            )
            >> self.generated_card.set_base_stats(attack=4, hp=6)
            >> SELF.turn_into(self.generated_card)
        )


@card(543)
class VendingMachine(Monster):
    generated_card: Var[Card] = Var(Card)

    def magic(self, ctx, **kwargs):
        tribe_monster_count = sum(
            1
            for monster in ctx.game.player(self.controller_id).board.cards
            if len(monster.template.tribes) > 0
        )

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Popato Chisps"))
        >> generated_card.buff(cost=-COUNT(BOARD & HAS_ANY_TRIBE))
        >> generated_card.to_hand()
    )


@card(545)
class Totem(Monster):
    _selector = DUSTPILE & ((COST == 7) | (BASE_HP == 7))

    need = COUNT(_selector) >= 7

    magic = (
        _selector[:5].erase()
        >> GENERATE_CARD("Totemic Carvings").to_hand()
    )


@card(547)
class MagicLantern(Monster):
    targets = ALLIES | ENEMIES

    magic = Check(COUNT(DUSTPILE) >= 6).to(
        DUSTPILE[:6].erase()
        >> TARGET.hit(4)
    )


@card(548)
class MagicCrystal(Monster):
    magic = For(
        4,
        effect=Cast(
            card=GENERATE_CARD("Gemstone"),
            controller=YOU,
            effect_target=ENEMY_MONSTERS >> RANDOM(1)
        )
    ) >> Check(
        SPENT_GOLD_ON_SPELLS_LAST_TURN
    ).to(
        GENERATE_CARD("Crystal Downpour").to_hand()
    )


@card(555)
class CoolVulkin(Monster):
    targets = ALLY_MONSTERS

    magic = (
        TARGET.buff(hp=+2)
        >> TARGET.add_keyword(TAUNT)
        >> FRONT(TARGET).hit(2)
    )


@card(558)
class Sushipants(Monster):
    need = ~EXISTS(
        DECK
        & NON_GENERATED
        & IS_MONSTER
        & (HAS_KEYWORD(HASTE) | HAS_KEYWORD(CHARGE))
    )

    magic = FRONT(SELF).paralyze()


@card(561)
class RoyalLoox(Monster):
    magic = ENEMIES.hit(1)

    @on_event(CardPlayedResult)
    def on_card_played(self, res: CardPlayedResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.cost < 6:
            return None

        card_ = game.entity(res.card_id)
        if not isinstance(card_, Monster):
            return None

        return ENEMIES.hit(1)


@card(572)
class PinkLaser(Monster):
    magic = SELF.set_base_stats(
        attack=SELF.base.attack + COUNT(
            CARDS_PLAYED(player=YOU)
            & IS_MONSTER
            & (BASE_HP == 7)
        )
    )


@card(580)
class TotemicGuard(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(
        COUNT((HAND | DUSTPILE) & IS_MONSTER & (COST == 6)) >= 3
    ).to(
        YOU.heal(5)
    )


@card(583)
class CrackedGeode(Monster):
    dust = ALL_MONSTERS.hit(2)


@card(601)
class Pickaxe(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        return GENERATE_CARD("Gemstone").to_hand()


@card(605)
class RiverBoat(Monster):
    card_1: Var[Card] = Var(Card)
    card_2: Var[Card] = Var(Card)
    card_3: Var[Card] = Var(Card)
    draw_result: Var[StepResult] = Var(StepResult)

    magic = (
        Check((COUNT(HAND) < MAX_HAND_SIZE) & (COUNT(DECK) > 0)).to(
            YOU.draw_next().store_result(draw_result).to(
                SetVar(var=card_1, value=RESOLVE_ENTITY(draw_result.card_id))
            )
        )
        >> Check((COUNT(HAND) < MAX_HAND_SIZE) & (COUNT(DECK) > 0)).to(
            YOU.draw_next().store_result(draw_result).to(
                SetVar(var=card_2, value=RESOLVE_ENTITY(draw_result.card_id))
            )
        )
        >> Check((COUNT(HAND) < MAX_HAND_SIZE) & (COUNT(DECK) > 0)).to(
            YOU.draw_next().store_result(draw_result).to(
                SetVar(var=card_3, value=RESOLVE_ENTITY(draw_result.card_id))
            )
        )
        >> SELF.schedule_delay_effect()
    )

    delay = (
        (card_1 & HAND).to_deck()
        >> (card_2 & HAND).to_deck()
        >> (card_3 & HAND).to_deck()
    )


@card(610)
class Trophy(Monster):
    dust = (
        YOU.add_artifact(ARTIFACT_BY_NAME("Economics"))
        >> YOU.artifact("Economics").update_artifact_counter(+3)
    )


@card(775)
class Crimeter(Monster):
    shock = SELF.force_attack((ENEMY_MONSTERS >> MIN(HP)).first())


@card(790)
class MettabotFactory(Monster):
    shock = Program(1).to(
        FillBoard(YOU, CARD_BY_NAME("Mettabot"))
    )


@card(804)
class RecycleBin(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(LOOP_COPY & (HAND | DECK)).to(
        Switch(
            left=LOOP_COPY.turn_into(
                (
                    CARD_LIBRARY
                    & IS_SPELL
                    & NON_TOKEN
                    & (COST == SELF.attack)
                ) >> RANDOM(1) >> GENERATE_CARD()
            ),
            right=LOOP_COPY.turn_into(
                (
                    CARD_LIBRARY
                    & IS_SPELL
                    & NON_TOKEN
                    & (COST == SELF.hp)
                ) >> RANDOM(1) >> GENERATE_CARD()
            )
        )
    )
