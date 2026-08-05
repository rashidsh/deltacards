from deltacards.dsl.api import *


@card(276)
class CattysDad(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.cost < 2:
            return None

        return YOU.earn_gold(1)


@card(277)
class Snailmobile(Monster):
    magic = YOU.draw((DECK & (COST <= 1)).first()) * 2


@card(279)
class Berdly(Monster):
    turn_end = ((HAND & IS_SPELL) >> RANDOM(2)).buff(cost=-1)


@card(282)
class GreatDoor(Monster):
    magic = GENERATE_CARD(
        "Petrified Monster",
        controller=OPPONENT
    ).summon(controller=OPPONENT)


@card(285)
class TutorialGuy(Monster):
    magic = YOU.choose(
        DISCOVER(
            RARITY == BASE,
            n=3,
        )
    ).to(
        CHOICE_SELECTED.buff(cost=-1)
        >> CHOICE_SELECTED.to_hand()
    )


@card(286)
class NurseMouth(Monster):
    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.cost < 2:
            return None

        return YOU.heal(3)


@card(288)
class Pippins(Monster):
    turbo = Check(COUNT(HAND) <= 6).to(
        YOU.draw_next()
    )


@card(289)
class RedWagon(Monster):
    targets = ALLY_MONSTERS

    released_card: Var[Card] = Var(Card)

    magic = SELF.catch(TARGET)

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.buff(attack=+3, hp=+3)
        >> released_card.to_deck(controller=YOU)
    )


@card(290)
class Snowy(Monster):
    targets = ALL_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)

    magic = (
        TARGET.hit(2).store_result(hit_result).to(
            Check(hit_result.killed).to(
                (
                    (CARD_LIBRARY & IS_SPELL & NON_TOKEN & (COST == hit_result.target.cost))
                    >> RANDOM(1)
                    >> GENERATE_CARD()
                ).to_hand()
            )
        )
    )


@card(291)
class NormalNPC(Monster):
    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        return SELF.paralyze()


@card(292)
class TheWarrior(Monster):
    magic = SELF.hit(5)


@card(293)
class ForestWorm(Monster):
    magic = Check(COUNT(OPPONENT_DUSTPILE & IS_MONSTER) >= 7).to(
        SELF.buff(attack=+2)
    )


@card(381)
class Catti(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        return (ENEMY_MONSTERS >> RANDOM(1)).hit(1)


@card(384)
class CloverHead(Monster):
    targets = ALLY_MONSTERS & HAS_ABILITY(TURBO)

    magic = (TARGET >> COPY()).to_deck(pos='top')


@card(385)
class EvilEye(Monster):
    _effect = GENERATE_CARD("Spying").to_hand()

    magic = _effect
    turn_start = _effect


@card(386)
class Pizzapants(Monster):
    played_count: Var[int] = Var(int)

    magic = SetVar(
        var=played_count,
        value=COUNT(
            CARDS_PLAYED(player=YOU)
            & (TEMPLATE_ID == SELF.template_id)
            & (CARD_ID != SELF.id)
        ),
    ) >> SELF.buff(attack=played_count, hp=played_count)


@card(395)
class TorielsCar(Monster):
    turbo = (
        (
            HAND
            & IS_MONSTER
            & HAS_ABILITY(TURBO)
        ) >> RANDOM(2)
    ).buff(cost=-1)

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        monster = game.entity(res.monster_id)
        if not isinstance(monster, Monster):
            return None

        if not monster.has_ability(Ability.TURBO):
            return None

        return (RESOLVE_ENTITY(res.monster_id) >> COPY()).to_deck()


@card(410)
class Bloxer(Monster):
    magic = YOU.choose(
        (
            DUSTPILE
            & IS_MONSTER
            & (COST <= 3)
        ) >> RANDOM(3)
    ).to(
        (CHOICE_SELECTED >> COPY()).summon()
        >> CHOICE_SELECTED.erase()
    )


@card(411)
class Animals(Monster):
    magic = Switch(
        left=SELF.add_keyword(HASTE),
        right=(DECK & IS_MONSTER)[:3].buff(attack=+1, hp=+1)
    )


@card(412)
class EvilBlueprints(Monster):
    magic = GENERATE_CARD("Thrashing Machine").to_hand()


@card(413)
class JumpingRabbit(Monster):
    dust = Check(TURN_PLAYER.id == YOU.id).to(
        YOU.draw_next()
        >> GENERATE_CARD("Jumping Rabbit").to_deck()
    )


@card(414)
class PurpleMascot(Monster):
    magic = (
        ENEMY_MONSTERS.add_keyword(KR)
        >> Program(3).to(
            ENEMY_MONSTERS.buff(attack=-1, hp=-1, min_hp=1)
        )
    )


@card(423)
class IceDrinkWolf(Monster):
    magic = YOU.choose(
        (
            CARD_BY_NAME("Ice")
            | CARD_BY_NAME("Ice Cap")
            | CARD_BY_NAME("Snowman")
        ) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(441)
class SwordEmblem(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        return Switch(
            left=SELF.set_status(DODGE, value=SELF.status(DODGE) + 1),
            right=SELF.add_keyword(TRANSPARENCY)
        )


@card(467)
class TopChef(Monster):
    cake: Var[Card] = Var(Card)
    spend_result: Var[StepResult] = Var(StepResult)

    magic = (
        SetVar(var=cake, value=GENERATE_CARD("Smolder Cake"))
        >> cake.set_base_stats(attack=1, hp=2)
        >> cake.summon()
        >> SpendGold(
            player=YOU,
            amount=2,
            allow_partial=True
        ).store_result(spend_result).to(
            cake.buff(
                attack=spend_result.amount,
                hp=spend_result.amount
            )
        )
    )


@card(469)
class BlocklerB(Monster):
    dust = GENERATE_CARD("Blockler O").summon()


@card(517)
class StuffedDoll(Monster):
    your_card: Var[Card] = Var(Card)
    enemy_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        DISCOVER(IS_MONSTER, NON_TOKEN, n=5)
    ).to(
        SetVar(var=your_card, value=CHOICE_SELECTED)
        >> SetVar(var=enemy_card, value=CHOICE_SELECTED >> COPY(controller=OPPONENT))
        >> your_card.buff(cost=-1)
        >> your_card.to_hand()
        >> enemy_card.to_hand(controller=OPPONENT)
    )


@card(520)
class AbstractArt(Monster):
    magic = (ALLY_MONSTERS & GENERATED).add_keyword(HASTE)


@card(527)
class DevilDoll(Monster):
    turbo = (ENEMY_MONSTERS >> RANDOM(1)).hit(1)

    magic = (ENEMY_MONSTERS & DAMAGED).hit(2)


@card(565)
class LancersBike(Monster):
    magic = ((HAND & IS_MONSTER) >> RANDOM(2)).buff(attack=+1)


@card(570)
class TheOriginal(Monster):
    need = ~EXISTS(DECK & NON_GENERATED & (RARITY == COMMON))

    magic = (HAND & IS_MONSTER).buff(attack=+1, hp=+1)


@card(594)
class ToyBricks(Monster):
    need = COUNT(DUSTPILE & (TEMPLATE_ID == SELF.template_id)) >= 4

    magic = (
        (DUSTPILE & (TEMPLATE_ID == SELF.template_id))[:4].erase()
        >> (GENERATE_CARD("Rescue Helicopter").to_deck() * 10)
    )


@card(607)
class SeatOfGods(Monster):
    magic = (
        Switch(
            left=(HAND & IS_MONSTER & (COST >= 9)).buff(cost=-1),
            right=(DECK & IS_MONSTER & (COST >= 9)).buff(cost=-1)
        )
        >> SELF.schedule_delay_effect()
    )

    delay = YOU.draw_next()


@card(612)
class AngelDoll(Monster):
    dust = ALLIES.buff(hp=+2)


@card(617)
class Maus(Monster):
    dust = GENERATE_CARD("Cursor").to_hand()


@card(621)
class MausCage(Monster):
    need = COUNT(
        DUSTPILE
        & IS_MONSTER
        & NON_GENERATED
        & (COST <= 1)
    ) >= 6

    magic = GENERATE_CARD("Mauswheel").to_hand()


@card(624)
class Tasque(Monster):
    other_cards_played = COUNT(
        CARDS_PLAYED(player=YOU, scope=THIS_TURN)
        & (BASE_COST >= 1)
        & (CARD_ID != SELF.id)
    )

    magic = SELF.buff(
        attack=other_cards_played,
        hp=other_cards_played
    )


@card(632)
class Trashy(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="+2 ATK on the enemy turn",
            applies=lambda q: q.monster is self and game.turn_player.id != self.controller_id,
            apply=lambda attack, q: attack + 2,
        )

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.PREVENT,
            source=self,
            description="Takes no DMG while attacking",
            applies=lambda q: (
                q.target is self
                and q.kind is DamageKind.COMBAT
                and q.combat_attacker is self
            ),
            apply=lambda damage, q: 0,
        )


@card(634)
class Pizzasimp(Monster):
    magic = Program(6).to(
        YOU.earn_gold(8)
    )


@card(639)
class Alterman(Monster):
    targets = ALLY_MONSTERS & ~SELF

    magic = TARGET.erase().to(
        SELF.buff(hp=+3)
    )


@card(644)
class CarnivalTent(Monster):
    magic = Cast(
        card=HAND & IS_SPELL & GENERATED,
        controller=YOU,
        effect_target='random'
    )


@card(646)
class Glitch(Monster):
    magic = (
        Switch(
            left=SELF.buff(attack=+2),
            right=SELF.buff(hp=+2)
        )
        >> Check((SELF.pos == 1) | (SELF.pos == 2)).to(
            SELF.swap_stats()
        )
    )


@card(649)
class BrokenCar(Monster):
    targets = ALL_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)

    magic = TARGET.hit(
        COUNT(ALL_MONSTERS & ~SELF)
    ).store_result(hit_result).to(
        Check(hit_result.amount <= 3).to(
            SELF.add_keyword(HASTE)
        )
    )


@card(653)
class Virovirokun(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if game.turn_player.id != self.controller_id:
            return None

        if res.target_id != self.controller_id:
            return None

        return SELF.buff(attack=+1, hp=+1)


@card(654)
class AmbyuLance(Monster):
    magic = (
        Check(YOU.hp < 15).to(
            SELF.buff(attack=+1) >> SELF.add_keyword(HASTE)
        )
        >> Check(YOU.hp < 10).to(
            SELF.add_keyword(CANDY) >> SELF.add_keyword(TAUNT)
        )
    )


@card(657)
class Iconman(Monster):
    targets = HAND

    magic = TARGET.erase().to(
        GENERATE_CARD("Recruitment").to_hand() * 2
    )


@card(661)
class CyberWorldSign(Monster):
    magic = (
        (
            DUSTPILE
            & IS_MONSTER
            & HAS_ABILITY(PROGRAM)
        )
        >> RANDOM(3)
        >> COPY()
    ).to_hand()


@card(666)
class StonedLancer(Monster):
    magic = SELF.paralyze()


@card(671)
class Berdlycoaster(Monster):
    need = EXISTS(HAND & TOKEN & (BASE_COST >= 3))

    magic = GENERATE_CARD("Feather Storm").to_hand()


@card(673)
class BerdlyPlush(Monster):
    magic = Check(HAND & TOKEN & (BASE_COST >= 3)).to(
        ((HAND & NON_TOKEN) >> RANDOM(3)).buff(cost=-1)
    )


@card(686)
class HangingPlug(Monster):
    targets = ALLY_MONSTERS & (COST <= 3)

    generated_card: Var[Card] = Var(Card)
    target_pos: Var[int] = Var(int)

    magic = (
        SetVar(var=target_pos, value=TARGET.pos)
        >> SetVar(var=generated_card, value=GENERATE_CARD("Werewire"))
        >> generated_card.set_base_stats(attack=2, hp=1)
        >> generated_card.catch(TARGET)
        >> generated_card.summon(pos=target_pos)
    )


@card(730)
class TheManual(Monster):
    magic = YOU.choose(
        (
            SPELLS_CAST(player=YOU)
            & (CARD_SOUL != None)
            & (CARD_SOUL != PLAYER_SOUL(player=YOU))
        )
        >> AS_TEMPLATES(distinct=True)
        >> RANDOM(3)
        >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.buff(cost=-2)
        >> CHOICE_SELECTED.to_hand()
    )


@card(753)
class Pipis(Monster):
    dust = GENERATE_CARD(
        "Hyperlink Blocked",
        controller=OPPONENT
    ).to_deck(controller=OPPONENT, pos='top') * 2


@card(761)
class BerdlyStatue(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.HAND:
            return

        played_token_count = 0

        for res in game.log_by_type[CardPlayedResult]:
            if res.player_id != self.controller_id:
                continue

            if res.card.template.rarity is not CardRarity.TOKEN:
                continue

            if res.card.cost < 1:
                continue

            played_token_count += 1

        if played_token_count <= 0:
            return

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="In your hand, this has -1 COST for each TOKEN card costing 1 or more GOLD you played this game (max: -8 COST)",
            applies=lambda q: q.card is self,
            apply=lambda cost, q: cost - min(played_token_count, 8),
        )


@card(763)
class ControlPanel(Monster):
    _effect = GENERATE_CARD("Shovel").to_hand()

    magic = _effect
    dust = _effect


@card(764)
class Swatchling(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Vase"))
        >> generated_card.add_keyword(TAUNT)
        >> generated_card.summon()
        >> Check(COUNT(ALLY_MONSTERS) < COUNT(ENEMY_MONSTERS)).to(
            generated_card.set_status(DODGE, value=1)
        )
    )


@card(767)
class BallDancer(Monster):
    magic = (
        (HAND | DECK)
        & IS_MONSTER
        & (COST <= SELF.cost)
    ).buff(cost=+1, attack=+1, hp=+1)


@card(768)
class SpaceStickers(Monster):
    targets = HAND & IS_MONSTER & HAS_ANY_TRIBE

    magic = TARGET.buff(attack=+1, hp=+1)


@card(776)
class TrafficLight(Monster):
    magic = (
        (((HAND | DECK) & DT) >> RANDOM(1)).buff(cost=-2)
        >> (((HAND | DECK) & (RARITY == LEGENDARY)) >> RANDOM(1)).buff(cost=-2)
        >> (((HAND | DECK) & TOKEN) >> RANDOM(1)).buff(cost=-2)
    )


@card(787)
class CyberTimer(Monster):
    _effect = Cast(
        card=GENERATE_CARD("Time Warp"),
        controller=YOU
    )

    magic = _effect
    turn_start = _effect


@card(887)
class Zapper(Monster):
    targets = ALL_MONSTERS

    need = SPENT_GOLD_ON_SPELLS_THIS_TURN

    magic = TARGET.erase()


@card(893)
class TreatCatcher(Monster):
    targets = (
        ALLY_MONSTERS
        & ~SELF
        & NON_TOKEN
        & (COST >= 2)
    )

    released_card: Var[Card] = Var(Card)

    magic = SELF.catch(TARGET).to(
        SELF.add_keyword(HASTE)
        >> SELF.add_keyword(CANDY)
        >> SELF.buff(attack=+1, hp=+1)
    )

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.to_hand(controller=YOU)
    )


@card(894)
class Winglade(Monster):
    magic = Check(ALL_MONSTERS & HAS_KEYWORD(TAUNT)).to(
        SELF.add_keyword(HASTE)
    )

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id == self.controller_id:
            return None

        if not (
            res.monster.has_keyword(HASTE)
            or res.monster.has_keyword(CHARGE)
        ):
            return None

        return SELF.force_attack(res.monster_id)


@card(906)
class PixelLanino(Monster):
    magic = (
        (DECK | HAND)
        & (TEMPLATE_NAME == "Pixel Elnina")
    ).first().summon()


@card(907)
class PixelElnina(Monster):
    magic = (
        (DECK | HAND)
        & (TEMPLATE_NAME == "Pixel Lanino")
    ).first().summon()


@card(915)
class CookingPoster(Monster):
    _food_stack = HAND & (TEMPLATE_NAME == "Food Stack")

    dust = Check(_food_stack).to(
        _food_stack.first().set_status(
            LOOP,
            value=_food_stack.first().status(LOOP) + 1
        ),
        else_=GENERATE_CARD("Food Stack").to_hand()
    )


@card(917)
class RockPoster(Monster):
    _spells_not_cast_yet = (
        CARD_LIBRARY
        & IS_SPELL
        & (CARD_SOUL == PLAYER_SOUL(player=YOU))
        & ~IN_HISTORY(SPELLS_CAST(player=YOU))
    )

    shock = Check(_spells_not_cast_yet).to(
        (_spells_not_cast_yet >> RANDOM(1) >> GENERATE_CARD()).to_hand(),
        else_=GENERATE_CARD("Rock Chord").to_hand()
    )


@card(919)
class MonsterPoster(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Susiezilla"))
        >> generated_card.buff(
            attack=COUNT(OPPONENT_DUSTPILE & IS_MONSTER) // 4,
            hp=COUNT(OPPONENT_DUSTPILE & IS_MONSTER) // 4
        )
        >> generated_card.to_hand()
    )


@card(921)
class Wicabel(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(SELF.hp == SELF.attack).to(
        SELF.buff(attack=+2)
        >> SELF.heal(SELF.max_hp)
    )


@card(922)
class CoolerCooler(Monster):
    shock = SELF.hit(1).to(
        GENERATE_CARD("Mizzle").summon()
    )


@card(925)
class Guei(Monster):
    magic = YOU.choose(
        (
            ((CARD_LIBRARY & IS_MONSTER & NON_TOKEN & HAS_ABILITY(DUST) & (COST == 1)) >> RANDOM(2))
            | ((CARD_LIBRARY & IS_MONSTER & NON_TOKEN & HAS_ABILITY(DUST) & (COST == 2)) >> RANDOM(2))
            | ((CARD_LIBRARY & IS_MONSTER & NON_TOKEN & HAS_ABILITY(DUST) & (COST == 3)) >> RANDOM(2))
        ) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.summon().to(
            CHOICE_SELECTED.kill()
        )
    )


@card(931)
class TitanFuzzy(Monster):
    shock = (
        SELF.buff(
            attack=TRIGGER_CARD.cost // 2,
            hp=TRIGGER_CARD.cost // 2
        )
        >> SELF.add_keyword(HASTE)
        >> SELF.refresh_attacks()
    )


@card(953)
class MausHand(Monster):
    targets = ALL_MONSTERS & (BASE_COST <= 2)

    magic = (TARGET >> COPY()).summon()


@card(960)
class Shinobeetle(Monster):
    bullseye = (
        SELF.buff(hp=+1)
        >> SELF.add_keyword(HASTE)
        >> SELF.refresh_attacks()
    )

    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        def other_ally_count() -> int:
            return sum(
                1
                for monster in game.player(self.controller_id).board.cards
                if (monster is not self)
            )

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="-1 ATK for each other ally monster",
            applies=lambda q: q.monster is self,
            apply=lambda attack, q: attack - other_ally_count(),
        )


@card(966)
class Hopschef(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(
            var=generated_card,
            value=GENERATE_CARD(
                "Sauerdough",
                controller=OPPONENT,
            )
        )
        >> generated_card.summon(
            controller=OPPONENT,
            attack=1,
            hp=2
        )
        >> SELF.schedule_delay_effect()
    )

    delay = Check(generated_card.dead).to(
        GENERATE_CARD("Sauerdough").summon(),
        else_=generated_card.kill()
    )


@card(974)
class MrButterfly(Monster):
    need = EXISTS(
        CARDS_PLAYED(player=YOU, scope=THIS_TURN)
        & (COST >= 6)
    )

    magic = GENERATE_CARD("Blue Rose").summon()


@card(985)
class GiantShrubbery(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        def is_adjacent_plant(monster: Monster) -> bool:
            return (
                monster.controller_id == self.controller_id
                and monster.zone is CardZone.BOARD
                and abs(monster.pos - self.pos) == 1
                and monster.has_tribe(Tribe.PLANT)
            )

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="Adjacent Plants have +2 ATK.",
            applies=lambda q: is_adjacent_plant(q.monster),
            apply=lambda attack, q: attack + 2,
        )

        yield IntModifier(
            kind=ModKind.MAX_HP,
            layer=StatLayer.ADD,
            source=self,
            description="Adjacent Plants have +2 max HP.",
            applies=lambda q: is_adjacent_plant(q.monster),
            apply=lambda max_hp, q: max_hp + 2,
        )
