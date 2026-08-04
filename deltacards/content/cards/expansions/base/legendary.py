from deltacards.dsl.api import *


@card(8)
class Toriel(Monster):
    targets = ENEMY_MONSTERS

    attack_delta: Var[int] = Var(int)

    magic = (
        SetVar(var=attack_delta, value=GREATEST(TARGET.attack - 1, 0))
        >> TARGET.set_stats(attack=1)
        >> SELF.buff(hp=attack_delta)
    )


@card(41)
class MadDummy(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.THRESHOLD,
            source=self,
            description="Can only be damaged by 4 or more DMG.",
            applies=lambda q: q.target is self,
            apply=lambda damage, q: damage if damage >= 4 else 0,
        )

    def magic(self, ctx, **kwargs):
        hit_result = yield ALL_MONSTERS.hit(3)

        excess_damage = 0
        for result in hit_result.results:
            if isinstance(result, EntityDamagedResult):
                excess_damage += result.excess_damage

        yield OPPONENT.hit(3)

        if excess_damage > 0:
            yield YOU.heal(excess_damage)


@card(52)
class Alphys(Monster):
    magic = (
        (
            CARD_LIBRARY
            & HAS_TRIBE(Tribe.ROYAL_INVENTION)
            & (CARD_SOUL == PLAYER_SOUL(player=YOU))
        ) >> GENERATE_CARD()
    ).to_hand()


@card(57)
class Gaster(Monster):
    magic = (
        ABILITY_TRIGGERS(controller=YOU, ability=SYNERGY)
        >> LIMIT_PER(TEMPLATE_ID, 2)
        >> AS_CARDS()
        >> COPY()
    ).trigger_ability(SYNERGY)


@card(58)
class Asriel(Monster):
    monster: Var[TargetSelector] = Var(TargetSelector)

    magic = ForEach(
        ALLY_MONSTERS & ~SELF,
        var=monster,
        effect=(
            monster.remove_negative_effects()
            >> monster.heal(monster.max_hp)
        )
    )


@card(59)
class Sans(Monster):
    _effect = GENERATE_CARD("Gaster Blaster").to_hand()

    magic = _effect
    turn_start = _effect


@card(60)
class Papyrus(Monster):
    magic = Program(2).to(
        SELF.add_keyword(ARMOR)
    )

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if res.attacker_dead:
            return None

        if not res.defender_dead:
            return None

        return SELF.refresh_attacks()


@card(61)
class Asgore(Monster):
    magic = (ALL_MONSTERS & DAMAGED).kill()


@card(63)
class AsrielDreemurr(Monster):
    magic = YOU.heal(30)


@card(64)
class MettatonEx(Monster):
    magic = Check(
        (YOU.gold >= 10) | (OPPONENT.gold >= 10)
    ).to(
        ALL_PLAYERS.set_gold(0)
    )


@card(110)
class MettatonNEO(Monster):
    dust = ENEMY_MONSTERS.hit(SELF.attack)


@card(214)
class CasualUndyne(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.source_id != self.id:
            return None

        target = game.entity(res.target_id)
        if not isinstance(target, Monster):
            return None

        return OPPONENT.hit(res.excess_damage)


@card(219)
class Gerson(Monster):
    magic = GENERATE_CARD("Junk for Sale").to_hand()


@card(254)
class CoolPapyrus(Monster):
    copied_card: Var[Card] = Var(Card)

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        if defender.template.rarity is CardRarity.DETERMINATION:
            return None

        return (
            SetVar(var=self.copied_card, value=RESOLVE_ENTITY(res.defender_id) >> COPY())
            >> self.copied_card.set_base_stats(cost=3, attack=4, hp=5)
            >> self.copied_card.to_hand()
        )


@card(262)
class MadMewMew(Monster):
    targets = ALLY_MONSTERS & NON_DT

    magic = (
        TARGET.halve_stats(round_up=False)
        >> (TARGET >> EXACT_COPY()).summon()
        >> Check(EMPTY_SLOTS(BOARD) > 0).to(
            Program(3).to(
                (TARGET >> EXACT_COPY()).summon()
            )
        )
    )


@card(427)
class KillerCook(Monster):
    X: Var[TargetSelector] = Var(TargetSelector)

    magic = ForEach(
        [CARD_BY_NAME("Flour"), CARD_BY_NAME("Eggs"), CARD_BY_NAME("Milk")],
        var=X,
        effect=(X >> GENERATE_CARD()).to_deck()
    )

    dust = YOU.draw((DECK & TOKEN).first())


@card(524)
class LegendaryArtifact(Monster):
    magic = FillHand(YOU, CARD_BY_NAME("Too Many Dogs"))


@card(564)
class GrillingKing(Monster):
    spincake_1: Var[Card] = Var(Card)
    spincake_2: Var[Card] = Var(Card)
    cake_1: Var[Card] = Var(Card)
    cake_2: Var[Card] = Var(Card)

    magic = (
        SetVar(var=spincake_1, value=GENERATE_CARD("Spincake"))
        >> SetVar(var=spincake_2, value=GENERATE_CARD("Spincake"))
        >> (spincake_1 | spincake_2).set_base_stats(attack=3, hp=3)
        >> (spincake_1 | spincake_2).summon()
        >> Check(COUNT(DECK) <= 3).to(
            SetVar(var=cake_1, value=GENERATE_CARD("Cake"))
            >> SetVar(var=cake_2, value=GENERATE_CARD("Cake"))
            >> (cake_1 | cake_2).set_base_stats(attack=5, hp=5)
            >> spincake_1.turn_into(cake_1)
            >> spincake_2.turn_into(cake_2)
        )
    )


@card(568)
class SansDog(Monster):
    magic = GENERATE_CARD("Bone", controller=OPPONENT).to_hand(controller=OPPONENT)


@card(579)
class BakingQueen(Monster):
    targets = ALL_MONSTERS & DAMAGED

    target_attack: Var[int] = Var(int)

    magic = (
        SetVar(var=target_attack, value=TARGET.attack)
        >> TARGET.kill().to(
            YOU.heal(target_attack)
        )
    )


@card(592)
class MioMioSan(Monster):
    magic = YOU.choose(
        OPPONENT_HAND & IS_MONSTER & NON_DT
    ).to(
        CHOICE_SELECTED.halve_stats(round_up=False)
        >> (CHOICE_SELECTED >> EXACT_COPY()).to_hand()
    )


@card(597)
class DTExtractor(Monster):
    magic = YOU.choose(
        (CARD_LIBRARY & DT) >> RANDOM(4) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(741)
class TheReflection(Monster):
    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=copied_cards,
            value=(
                ENEMY_MONSTERS
                & NON_DT
                & (TEMPLATE_ID != SELF.template_id)
            ) >> COPY()
        )
        >> copied_cards.buff(cost=-2)
        >> copied_cards.to_hand()
    )


@card(770)
class ReporterMTT(Monster):
    targets = (
        ALLY_MONSTERS
        & NON_DT
        & (TEMPLATE_ID != SELF.template_id)
    )

    returned_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=returned_card, value=TARGET)
        >> TARGET.to_hand().to(
            TARGET.buff(cost=-8)
            >> SELF.schedule_delay_effect()
        )
    )

    delay = (returned_card & (HAND | DECK)).erase()


@card(777)
class DogSlots(Monster):
    magic = (
        HAND.to_deck()
        >> (GENERATE_CARD("Arcane Codes").to_hand() * 7)
    )


@card(848)
class CasinoSans(Monster):
    random_card: Var[Card] = Var(Card)

    magic = (
        Check(EMPTY_SLOTS(BOARD) > 0).to(
            SetVar(
                var=random_card,
                value=(CARD_LIBRARY & TOKEN) >> RANDOM(1) >> GENERATE_CARD()
            ),
            else_=SetVar(
                var=random_card,
                value=(CARD_LIBRARY & IS_SPELL & TOKEN) >> RANDOM(1) >> GENERATE_CARD()
            )
        )
        >> Check(random_card & IS_MONSTER).to(
            random_card.summon(),
            else_=Cast(
                card=random_card,
                controller=YOU,
                effect_target='random'
            )
        )
    )


@card(874)
class ElUndercardio(Monster):
    _random_pack = (
        CARD_BY_NAME("Pack")
        | CARD_BY_NAME("Super Pack")
        | CARD_BY_NAME("Final Pack")
    ) >> WEIGHTED_RANDOM(75, 20, 5)

    magic = FillHand(YOU, _random_pack)


@card(941)
class JogboyPapyrus(Monster):
    magic = ENEMY_SLOTS.enchant(
        ENCHANTMENT_BY_NAME('blue-bones')
    )
