from deltacards.dsl.api import *


@card(266)
class CloverHydra(Monster):
    targets = ALLIES | ENEMIES

    magic = (
        TARGET.hit(3)
        >> (YOU.draw_next() * 3)
        >> YOU.heal(3)
    )


@card(267)
class CrystalTombstone(Monster):
    dustpile_cards: Var[TargetSelector] = Var(TargetSelector)
    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=dustpile_cards,
            value=(
                (
                    DUSTPILE
                    & IS_MONSTER
                    & NON_GENERATED
                    & (COST <= 7)
                )
                >> RANDOM(2)
           )
        )
        >> SetVar(var=copied_cards, value=dustpile_cards >> COPY())
        >> dustpile_cards.erase()
        >> copied_cards.summon()
    )


@card(271)
class ChaosDuck(Monster):
    targets = ALL_MONSTERS

    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Apoca Duck"))
        >> generated_card.add_keyword(HASTE)
        >> TARGET.turn_into(generated_card)
    )


@card(272)
class GardenerAsgore(Monster):
    generated_card: Var[Card] = Var(Card)

    _stat_buff = COUNT(DUSTPILE & IS_MONSTER & HAS_TRIBE(Tribe.PLANT)) // 4

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Red Flower"))
        >> generated_card.buff(attack=_stat_buff, hp=_stat_buff)
        >> generated_card.summon()
    )


@card(318)
class FatherAlvin(Monster):
    magic = YOU.choose(
        (
            DUSTPILE
            & IS_MONSTER
            & NON_DT
        ) >> RANDOM(3)
    ).to(
        (CHOICE_SELECTED >> COPY()).to_hand()
        >> CHOICE_SELECTED.erase()
    )


@card(378)
class CRound(Monster):
    dust = Check(SELF & NON_GENERATED).to(
        (GENERATE_CARD("Crown").to_deck() * 2)
        >> GENERATE_CARD("C-Round").to_hand()
    )


@card(416)
class DadDragon(Monster):
    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if res.monster.template.name == "Dragon Kid":
            return None

        return GENERATE_CARD("Dragon Kid").summon()


@card(417)
class Jockington(Monster):
    shock = YOU.draw_next()


@card(418)
class Malius(Monster):
    targets = HAND

    magic = TARGET.to_deck()


@card(425)
class DarkThrone(Monster):
    magic = YOU.draw((DECK & GENERATED).first())


@card(443)
class SpadeChain(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.hit(4 + (TARGET.cost // 3))


@card(468)
class Rudolph(Monster):
    need = ~EXISTS(DECK & NON_GENERATED & IS_SPELL)

    magic = YOU.heal(5)


@card(506)
class SoulCage(Monster):
    generated_card: Var[Card] = Var(Card)

    dust = (
        SetVar(var=generated_card, value=GENERATE_CARD("Knife", controller=TURN_PLAYER))
        >> generated_card.set_stats(cost=0)
        >> generated_card.to_hand(controller=TURN_PLAYER)
    )


@card(515)
class HeadHathy(Monster):
    need = SPENT_GOLD_ON_SPELLS_LAST_TURN

    magic = (
        GENERATE_CARD("Breaking Love").to_hand()
        >> GENERATE_CARD("Breaking Love").to_deck()
    )


@card(533)
class GersonTombstone(Monster):
    need = (
        COUNT(DECK & NON_GENERATED)
        == COUNT_DISTINCT(DECK & NON_GENERATED, TEMPLATE_ID)
    )

    magic = (
        (
            DUSTPILE
            & IS_MONSTER
            & (COST >= 5)
            & (COST <= 7)
            & (TEMPLATE_ID != SELF.template_id)
        ) >> RANDOM(1) >> COPY()
    ).summon()


@card(549)
class CopUndyne(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return ADJACENT(RESOLVE_ENTITY(res.defender_id)).hit(2)


@card(573)
class EliminationDuck(Monster):
    monster: Var[Card] = Var(Card)

    magic = ForEach(
        ALL_MONSTERS & ~SELF,
        var=monster,
        effect=(
            monster.turn_into(
                (
                    CARD_LIBRARY
                    & IS_MONSTER
                    & NON_TOKEN
                    & (COST == monster.cost)
                    & (TEMPLATE_ID != monster.template_id)
                ) >> RANDOM(1) >> GENERATE_CARD(
                    controller=CONTROLLER_OF(monster)
                )
            )
        )
    )


@card(581)
class GoldenMascot(Monster):
    dust = GENERATE_CARD("Final Pack").to_hand()


@card(584)
class CagedKings(Monster):
    need = SPENT_GOLD_ON_SPELLS_LAST_TURN

    magic = (
        GENERATE_CARD("Broken Key").to_deck()
        >> YOU.draw_next()
    )


@card(626)
class TasqueManager(Monster):
    cards_to_move: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=cards_to_move,
            value=(DECK & NON_TOKEN) >> MIN(COST, 3)
        )
        >> cards_to_move.buff(cost=-1)
        >> cards_to_move.to_deck(pos='top')
    )


@card(630)
class ShovelsX999(Monster):
    turn_end = (
        (
            HAND
            & NON_GENERATED
        ) >> MIN(COST)
    ).turn_into(
        GENERATE_CARD("Shovel")
    )


@card(635)
class SusieStatue(Monster):
    turn_start = SELF.force_attack(ENEMY_MONSTERS >> RANDOM(1))


@card(642)
class Policeblook(Monster):
    dust = GENERATE_CARD("Prison Bars").to_hand()


@card(645)
class ArcadeMachine(Monster):
    need = COUNT(HAND) == COUNT_DISTINCT(HAND, RARITY)

    magic = HAND.buff(cost=-3)


@card(647)
class QueenPainting(Monster):
    generated_card: Var[Card] = Var(Card)

    support = (
        SetVar(var=generated_card, value=GENERATE_CARD("Spamton Painting"))
        >> generated_card.set_base_stats(
            cost=SELF.base.cost,
            attack=SELF.base.attack,
            hp=SELF.base.hp
        )
        >> SELF.turn_into(generated_card)
    )


@card(652)
class SusiePlush(Monster):
    magic = (
        Check(YOU.hp <= 10).to(
            ENEMIES.hit(2),
            else_=YOU.hit(2)
        )
    )


@card(655)
class Nubert(Monster):
    magic = For(
        COUNT_UNIQUE_TRIBES(DUSTPILE & IS_MONSTER),
        ((HAND & IS_MONSTER) >> RANDOM(1)).buff(attack=+1, hp=+1)
    )


@card(656)
class Cybershelf(Monster):
    magic = YOU.choose(
        (
            CARD_LIBRARY
            & IS_SPELL
            & NON_TOKEN
            & (CARD_SOUL == PLAYER_SOUL(player=OPPONENT))
        ) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(674)
class Halberd(Monster):
    need = COUNT(
        CARDS_PLAYED(player=YOU)
        & TOKEN
        & (BASE_COST >= 3)
    ) >= 3

    magic = GENERATE_CARD("Halberd").summon()


@card(757)
class PipisCannon(Monster):
    cards_to_erase: Var[TargetSelector] = Var(TargetSelector)
    erased_count: Var[int] = Var(int)
    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(
            var=cards_to_erase,
            value=(OPPONENT_DECK & (TEMPLATE_NAME == "Hyperlink Blocked"))[:9]
        )
        >> SetVar(var=erased_count, value=COUNT(cards_to_erase))
        >> cards_to_erase.erase()
        >> For(
            erased_count // 3,
            (
                SetVar(var=generated_card, value=GENERATE_CARD("Ms Pipis"))
                >> generated_card.add_keyword(CHARGE)
                >> generated_card.summon()
            )
        )
    )


@card(758)
class BrokenNEO(Monster):
    targets = ENEMY_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)

    need = COUNT(OPPONENT_DECK & (TEMPLATE_NAME == "Hyperlink Blocked")) >= 10

    magic = (
        OPPONENT_DECK & (TEMPLATE_NAME == "Hyperlink Blocked")
    )[:10].erase().to(
        TARGET.hit(10).store_result(hit_result).to(
            ENEMIES.hit(hit_result.excess_damage)
        )
    )


@card(759)
class TasqueSinger(Monster):
    magic = (
        ENEMY_MONSTERS
        & (COST <= COUNT(CARDS_PLAYED(player=YOU, scope=THIS_TURN) & NON_TOKEN))
    ).kill()


@card(769)
class ManeAx(Monster):
    targets = ALL_MONSTERS

    magic = (
        TARGET.silence()
        >> TARGET.buff(attack=-2, hp=-1)
    )


@card(773)
class ShyraTombstone(Monster):
    need = COUNT(DUSTPILE & IS_MONSTER) >= 7

    magic = SELF.buff(hp=+3)


@card(774)
class DisguisedLancer(Monster):
    monster: Var[Card] = Var(Card)
    monster_pos: Var[int] = Var(int)
    monster_attack: Var[int] = Var(int)
    monster_hp: Var[int] = Var(int)

    magic = ForEach(
        ALLY_MONSTERS & ~SELF & NON_DT,
        var=monster,
        effect=(
            SetVar(var=monster_pos, value=monster.pos)
            >> SetVar(var=monster_attack, value=monster.attack)
            >> SetVar(var=monster_hp, value=monster.hp)
            >> monster.to_hand().to(
                GENERATE_CARD("Thrashing Machine").summon(
                    pos=monster_pos,
                    attack=monster_attack,
                    hp=monster_hp
                )
            )
        )
    )


@card(779)
class SansDeltarune(Monster):
    spell_to_transform: Var[Card] = Var(Card)

    magic = Switch(
        left=Check(HAND & IS_SPELL & (COST >= 1)).to(
            SetVar(
                var=spell_to_transform,
                value=(HAND & IS_SPELL & (COST >= 1)) >> RANDOM(1)
            )
            >> spell_to_transform.reveal()
            >> spell_to_transform.turn_into(
                GENERATE_CARD(
                    "Gaster Blaster",
                    controller=CONTROLLER_OF(spell_to_transform)
                )
            )
        ),
        right=Check(OPPONENT_HAND & IS_SPELL & (COST >= 1)).to(
            SetVar(
                var=spell_to_transform,
                value=(OPPONENT_HAND & IS_SPELL & (COST >= 1)) >> RANDOM(1)
            )
            >> spell_to_transform.reveal()
            >> spell_to_transform.turn_into(
                GENERATE_CARD(
                    "Gaster Blaster",
                    controller=CONTROLLER_OF(spell_to_transform)
                )
            )
        )
    )


@card(791)
class GiantToilet(Monster):
    need = (
        (~SELF.is_generated)
        & (~EXISTS((HAND | DECK) & ~SELF))
    )

    magic = (
        SELF.buff(attack=+90, hp=+90)
        >> SELF.add_keyword(CHARGE)
    )


@card(792)
class Noellecoaster(Monster):
    spell_count: Var[int] = Var(int)

    magic = (
        SetVar(
            var=spell_count,
            value=COUNT(SPELLS_CAST(player=YOU) & (BASE_COST >= 2))
        )
        >> YOU.choose(
            DISCOVER(
                IS_SPELL,
                NON_TOKEN,
                (COST == spell_count),
                n=3
            )
        ).to(
            SELF.buff(attack=spell_count, hp=spell_count)
            >> Cast(
                card=CHOICE_SELECTED,
                controller=YOU,
                effect_target=FRONT(SELF)
            )
        )
    )

    def iter_modifiers(self, game):
        if self.zone is not CardZone.HAND:
            return

        spell_count = sum(
            1
            for res in game.log_by_type[SpellCastResult]
            if (
                res.player_id == self.controller_id
                and res.is_played
                and res.card.base.cost >= 2
            )
        )

        if spell_count <= 0:
            return

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="+1 COST in hand for each 2+ GOLD spell you cast this game",
            applies=lambda q: q.card is self,
            apply=lambda cost, q: cost + spell_count,
        )


@card(807)
class Spamequin(Monster):
    generated_card: Var[Card] = Var(Card)

    _effect = (
        SetVar(var=generated_card, value=GENERATE_CARD("Pipis"))
        >> generated_card.add_keyword(HASTE)
        >> generated_card.to_hand()
    )

    magic = _effect
    dust = _effect
    shock = _effect
    turn_start = _effect


@card(883)
class PixelLancer(Monster):
    delay = Cast(
        card=GENERATE_CARD("Spade"),
        controller=YOU,
        effect_target=ENEMY_MONSTERS >> MIN(HP)
    )


@card(884)
class PixelSusie(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.set_stats(attack=3, hp=3)


@card(885)
class ZootKris(Monster):
    magic = GENERATE_CARD("Sharpshoot").to_hand()


@card(888)
class WhiteCloak(Monster):
    generated_card: Var[Card] = Var(Card)

    need = COUNT(DUSTPILE & IS_MONSTER & TOKEN) >= 7

    magic = (
        (DUSTPILE & IS_MONSTER & TOKEN)[:7].erase().to(
            SetVar(var=generated_card, value=GENERATE_CARD("Ice Crystal"))
            >> generated_card.set_stats(cost=2)
            >> generated_card.to_hand()
        )
    )


@card(892)
class Knightdyne(Monster):
    generated_card: Var[Card] = Var(Card)

    def magic(self, ctx, **kwargs):
        for _ in range(4):
            opponent = ctx.game.player(self.controller_id).opponent
            if len(opponent.board.cards) == 0:
                return None

            step = yield (ENEMY_MONSTERS >> MIN(HP)).hit(1)

            killed = False
            for result in step.results:
                if isinstance(result, EntityDamagedResult):
                    killed = result.killed

            if killed:
                yield (
                    SetVar(var=self.generated_card, value=GENERATE_CARD("Spear"))
                    >> self.generated_card.set_base_stats(attack=2, hp=3)
                    >> self.generated_card.add_keyword(TAUNT)
                    >> self.generated_card.summon()
                )


@card(898)
class TitanSerpent(Monster):
    copied_card: Var[Card] = Var(Card)

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if res.attacker_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return (
            SetVar(var=self.copied_card, value=SELF >> EXACT_COPY())
            >> self.copied_card.add_keyword(HASTE)
            >> self.copied_card.halve_stats(round_up=False)
            >> self.copied_card.summon()
        )


@card(903)
class ZootSusie(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.hit(4)

    bullseye = (
        ADJACENT(TARGET).hit(3)
        >> GENERATE_CARD("Recruitment").to_hand()
    )


@card(904)
class ZootRalsei(Monster):
    targets = ENEMY_MONSTERS

    copied_card: Var[Card] = Var(Card)

    magic = (
        TARGET.add_keyword(WANTED)
        >> TARGET.hit(1)
    )

    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id == self.controller_id:
            return None

        if not res.monster.has_keyword(WANTED):
            return None

        return (
            SetVar(var=self.copied_card, value=RESOLVE_ENTITY(res.monster_id) >> COPY())
            >> self.copied_card.set_base_stats(attack=2, hp=3)
            >> self.copied_card.summon()
        )


@card(908)
class RockstarRalsei(Monster):
    support = DrawUpTo(1)

    shock = (DECK & IS_MONSTER).first().buff(cost=-1)


@card(909)
class RockstarKris(Monster):
    shock = SELF.toggle_ability(SUPPORT, True)

    support = (
        SELF.buff(attack=+2, hp=+2)
        >> SELF.toggle_ability(SUPPORT, False)
    )


@card(910)
class GoldenPiano(Monster):
    bonus: Var[int] = Var(int)

    magic = (
        SetVar(var=bonus, value=COUNT_DISTINCT(DUSTPILE & IS_MONSTER, COST) // 2)
        >> SELF.buff(attack=bonus, hp=bonus)
    )


@card(914)
class Cuptower(Monster):
    generated_card: Var[Card] = Var(Card)

    dust = For(
        3,
        (
            SetVar(var=generated_card, value=GENERATE_CARD("Cuptain"))
            >> generated_card.add_keyword(HASTE)
            >> generated_card.summon()
        )
    )


@card(923)
class PixelKris(Monster):
    need = EXISTS(
        MONSTERS_DIED(scope=THIS_TURN)
        & (BASE_COST >= 2)
    )

    magic = Check(FRONT(SELF)).to(
        SELF.buff(attack=FRONT(SELF).attack)
        >> Cast(
            card=GENERATE_CARD("Proceed"),
            controller=YOU,
            effect_target=FRONT(SELF)
        )
    )


@card(927)
class GachaponMachine(Monster):
    magic = YOU.choose(
        DISCOVER(
            IS_MONSTER,
            NON_DT,
            NON_TOKEN,
            (COST == LEAST(OPPONENT.gold, 15)),
            n=5
        )
    ).to(
        CHOICE_SELECTED.summon()
    )


@card(946)
class TallBloxer(Monster):
    dustpile_cards: Var[TargetSelector] = Var(TargetSelector)
    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=dustpile_cards,
            value=(
                (
                        DUSTPILE
                        & IS_MONSTER
                        & NON_TOKEN
                        & (COST <= 3)
                )
                >> RANDOM(3)
           )
        )
        >> SetVar(var=copied_cards, value=dustpile_cards >> COPY())
        >> dustpile_cards.erase()
        >> copied_cards.summon()
    )


@card(952)
class MissMizzle(Monster):
    _effect = GENERATE_CARD("Mizzle").to_hand()

    magic = _effect
    dust = _effect

    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.HEAL,
            layer=HealLayer.ADD,
            source=self,
            description="Monsters heal 2 more HP to allies",
            applies=lambda q: (
                isinstance(q.source, Monster)
                and q.target.controller_id == self.controller_id
            ),
            apply=lambda amount, q: amount + 2,
        )


@card(958)
class RockstarSusie(Monster):
    shock = (
        (SELF | ENEMIES).hit(2)
        >> SELF.toggle_ability(SHOCK, False)
    )

    support = (
        SELF.heal(SELF.max_hp)
        >> SELF.toggle_ability(SHOCK, True)
    )


@card(962)
class TrialKris(Monster):
    magic = SELF.schedule_delay_effect()

    delay = (
        YOU.add_artifact(
            ARTIFACT_BY_NAME("True Justice")
        )
        >> YOU.artifact("True Justice").update_artifact_counter(
            COUNT(MONSTERS_DIED(scope=THIS_TURN))
        )
    )


@card(971)
class DuckOfDoom(Monster):
    bullseye = (ALL_MONSTERS & ~SELF).kill()


@card(973)
class TrialSusie(Monster):
    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if res.attacker_dead:
            return None

        return (
            (ALL_MONSTERS & ~SELF).set_stats(hp=SELF.hp)
            >> SELF.silence()
        )


@card(975)
class TrialRalsei(Monster):
    magic = SELF.schedule_delay_effect()

    delay = (
        (
            MONSTERS_DIED(
                controller=YOU,
                scope=THIS_TURN
            )
            & NON_DT
        )
        >> AS_CARDS()
        >> COPY()
    ).summon(attack=3, hp=3)
