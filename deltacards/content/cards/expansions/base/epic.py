from deltacards.dsl.api import *


@card(53)
class Napstablook(Monster):
    turn_end = (
        SELF.buff(attack=-1)
        >> Check(SELF.attack <= 0).to(
            SELF.kill()
        )
    )


@card(56)
class Mettaton(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.CAP,
            source=self,
            description="Can only take up to 3 DMG at a time",
            applies=lambda q: q.target is self,
            apply=lambda damage, q: min(damage, 3),
        )


@card(104)
class Grillby(Monster):
    magic = (ALLY_MONSTERS & ~SELF).buff(attack=+1, hp=+1)


@card(123)
class Onionsan(Monster):
    left_tentacle: Var[Card] = Var(Card)
    right_tentacle: Var[Card] = Var(Card)

    magic = (
        SetVar(var=left_tentacle, value=GENERATE_CARD("Left Tentacle"))
        >> left_tentacle.buff(attack=+2, hp=+2)
        >> left_tentacle.summon(pos=SELF.pos - 1)
        >> SetVar(var=right_tentacle, value=GENERATE_CARD("Right Tentacle"))
        >> right_tentacle.buff(attack=+2, hp=+2)
        >> right_tentacle.summon(pos=SELF.pos + 1)
    )


@card(152)
class Bratty(Monster):
    erased_spell: Var[Card] = Var(Card)
    erased_cost: Var[int] = Var(int)

    magic = Check(HAND & IS_SPELL).to(
        SetVar(var=erased_spell, value=(HAND & IS_SPELL) >> RANDOM(1))
        >> SetVar(var=erased_cost, value=((HAND & IS_SPELL) >> RANDOM(1)).cost)
        >> erased_spell.erase().to(
            YOU.choose(
                (CARD_LIBRARY & IS_SPELL & NON_TOKEN & (COST == erased_cost))
                >> GENERATE_CARD()
            ).to(
                CHOICE_SELECTED.to_hand()
                >> (HAND & IS_SPELL).buff(cost=-1)
            )
        )
    )


@card(153)
class Catty(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        return Check(COUNT(HAND) <= 5).to(
            YOU.draw_next()
        )


@card(154)
class RiverPerson(Monster):
    magic = (
        For(
            6,
            Check((COUNT(HAND) < 6) & (COUNT(DECK) > 0)).to(
                YOU.draw_next()
            )
        )
        >> For(
            6,
            Check((COUNT(OPPONENT_HAND) < 6) & (COUNT(OPPONENT_DECK) > 0)).to(
                OPPONENT.draw_next()
            )
        )
    )


@card(170)
class Loren(Monster):
    magic = GENERATE_CARD("Star").summon() * 3


@card(192)
class BigBomb(Monster):
    magic = GENERATE_CARD("Mine", controller=OPPONENT).to_deck(controller=OPPONENT) * 3


@card(201)
class DancerMettaton(Monster):
    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return YOU.heal(4) >> GENERATE_CARD("Mettabot").summon()


@card(202)
class Innkeeper(Monster):
    magic = YOU.buff(hp=+5)


@card(218)
class Receptionist3(Monster):
    magic = ((OPPONENT_HAND & IS_MONSTER) >> RANDOM(1)).summon(controller=OPPONENT)


@card(229)
class SnailTrainer(Monster):
    need = COUNT(DUSTPILE & HAS_TRIBE(Tribe.SNAIL)) >= 10

    magic = GENERATE_CARD("Thundersnail").to_hand()


@card(249)
class Robot98(Monster):
    turn_end = SELF.set_status(
        DODGE,
        value=GREATEST(SELF.status(DODGE) - 97, 0)
    )


@card(250)
class HotDogHarpy(Monster):
    targets = ENEMY_MONSTERS

    magic = Check(TARGET & HAS_KEYWORD(SILENCED)).to(
        TARGET.kill(),
        else_=TARGET.silence()
    )


@card(252)
class Throne(Monster):
    magic = YOU.draw(
        (
            DECK
            & NON_DT
            & NON_TOKEN
            & (TEMPLATE_ID != SELF.template_id)
        ) >> MAX(RARITY)
    )


@card(466)
class Bookshelf(Monster):
    need = ~EXISTS(DECK & NON_GENERATED & IS_SPELL)

    magic = YOU.choose(
        (
            CARD_LIBRARY
            & IS_SPELL
            & NON_TOKEN
            & (CARD_SOUL == PLAYER_SOUL(player=YOU))
        ) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.buff(cost=-2)
        >> CHOICE_SELECTED.to_hand()
    )


@card(502)
class MysteryMachine(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.kill().to(
        GENERATE_CARD("Gaster Blaster").to_hand()
    )


@card(503)
class LibraryLoox(Monster):
    targets = ALLIES | ENEMIES

    need = (
        COUNT(DECK & NON_GENERATED)
        == COUNT_DISTINCT(DECK & NON_GENERATED, TEMPLATE_ID)
    )

    magic = TARGET.hit(EMPTY_SLOTS(HAND))


@card(514)
class DateAlphys(Monster):
    targets = ALLY_MONSTERS

    magic = (
        TARGET.add_keyword(HASTE)
        >> TARGET.refresh_attacks()
    )


@card(526)
class PlatedPipe(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="Takes 1 less DMG during the enemy turn",
            applies=lambda q: (
                q.target is self
                and game.turn_player.id != self.controller_id
            ),
            apply=lambda damage, q: damage - 1,
        )

    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.target_id != self.id:
            return None

        return OPPONENT.hit(1)


@card(530)
class Piranhas(Monster):
    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return self._repeat_random_hit

    def _repeat_random_hit(self, ctx, **kwargs):
        while True:
            if len(ctx.game.player(self.controller_id).opponent.board.cards) == 0:
                return None

            step = yield (ENEMY_MONSTERS >> RANDOM(1)).hit(1)

            killed = False
            for result in step.results:
                if isinstance(result, EntityDamagedResult):
                    killed = result.killed

            if not killed:
                return None


@card(556)
class Baron(Monster):
    magic = (ALLY_MONSTERS & ~SELF).buff(attack=+2)


@card(588)
class Spaghetti(Monster):
    shock = YOU.heal(3)


@card(593)
class Rapstablook(Monster):
    turn_start = SELF.kill().to(
        ENEMIES.hit(3)
    )


@card(603)
class PinkCrystals(Monster):
    magic = GENERATE_CARD("Gemstone").to_hand()

    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.template.name != "Gemstone":
            return None

        return FRONT(SELF).buff(attack=-1, hp=-1)


@card(608)
class VoidLaser(Monster):
    magic = GENERATE_CARD("Gaster Blaster").to_deck() * 2

    turn_end = (
        (DECK & (TEMPLATE_NAME == "Gaster Blaster"))
        >> RANDOM(2)
    ).buff(cost=-1)


@card(609)
class GMachine(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(SELF.dead).to(
        GENERATE_CARD("Gaster Blaster").to_hand()
    )


@card(740)
class FriskLaser(Monster):
    generated_card: Var[Card] = Var(Card)

    @on_event(CardDrawnResult)
    def on_card_drawn(self, res: CardDrawnResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        return (
            SetVar(
                var=self.generated_card,
                value=(
                    CARD_LIBRARY
                    & EXPANSION(Expansion.BASE)
                    & (RARITY == LEGENDARY)
                ) >> RANDOM(1) >> GENERATE_CARD()
            )
            >> TransformCard(target=res.card_id, new_card=self.generated_card)
            >> self.generated_card.buff(cost=-2)
        )


@card(745)
class StageLights(Monster):
    copied_card: Var[Card] = Var(Card)

    magic = (
        SetVar(
            var=copied_card,
            value=(
                OPPONENT_HAND
                & IS_MONSTER
                & NON_DT
                & (TEMPLATE_ID != SELF.template_id)
            ) >> MAX(COST) >> COPY()
        )
        >> copied_card.to_hand()
    )


@card(766)
class LargeChest(Monster):
    generated_cards: Var[TargetSelector] = Var(TargetSelector)

    need = COUNT_DISTINCT(DUSTPILE, RARITY) >= 6

    magic = (
        (DUSTPILE >> DISTINCT(RARITY))[:6].erase()
        >> SetVar(
            var=generated_cards,
            value=(CARD_LIBRARY & IS_MONSTER & NON_TOKEN) >> RANDOM(6) >> GENERATE_CARD()
        )
        >> generated_cards.buff(cost=-2, attack=+1, hp=+1)
        >> generated_cards.to_hand()
    )


@card(781)
class GiftBomb(Monster):
    dust = ((HAND & IS_MONSTER & (BASE_COST <= 3)) >> RANDOM(2)).summon()


@card(784)
class LabSign(Monster):
    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        HAND.to_deck()
        >> SetVar(
            var=copied_cards,
            value=(
                DUSTPILE
                & HAS_TRIBE(Tribe.AMALGAMATE)
            ) >> DISTINCT(TEMPLATE_ID) >> COPY()
        )
        >> copied_cards.buff(cost=-1, attack=+1, hp=+1)
        >> copied_cards.to_hand()
    )


@card(802)
class MewMewWand(Monster):
    targets = ENEMY_MONSTERS

    magic = Switch(
        left=(
            TARGET.buff(attack=-2)
            >> LOOP_COPY.buff(attack=+2)
        ),
        right=(
            TARGET.buff(hp=-2)
            >> LOOP_COPY.buff(hp=+2)
        )
    )


@card(806)
class Torch(Monster):
    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.is_generated:
            return None

        return OPPONENT.hit(1)


@card(871)
class IceE(Monster):
    targets = ALL_MONSTERS

    magic = (
        TARGET.paralyze()
        >> Check(TARGET & ALLY_MONSTERS & (COST >= 2)).to(
            GENERATE_CARD("Ice").summon() * 2
        )
    )


@card(940)
class StrangeMachine(Monster):
    magic = (
        ENEMY_SLOTS[0].enchant(
            ENCHANTMENT_BY_NAME('green-tile')
        )
        >> ENEMY_SLOTS[1].enchant(
            ENCHANTMENT_BY_NAME('yellow-tile')
        )
        >> ENEMY_SLOTS[2].enchant(
            ENCHANTMENT_BY_NAME('purple-tile')
        )
        >> ENEMY_SLOTS[3].enchant(
            ENCHANTMENT_BY_NAME('orange-tile')
        )
    )

    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="This takes 1 less DMG for each enemy slot enchantment",
            applies=lambda q: q.target is self,
            apply=lambda damage, q: damage - len(
                q.game.active_enchantments(
                    q.game.player(self.controller_id).opponent
                )
            ),
        )


@card(942)
class WallOfFire(Monster):
    magic = (
        ENEMY_SLOTS
        & EMPTY_SLOT
        & UNENCHANTED_SLOT
    ).enchant(
        ENCHANTMENT_BY_NAME('the-flame')
    )


@card(943)
class FireE(Monster):
    targets = ALLY_SLOTS

    magic = TARGET.enchant(
        ENCHANTMENT_BY_NAME('incinerator')
    )
