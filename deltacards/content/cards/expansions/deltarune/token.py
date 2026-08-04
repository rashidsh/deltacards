from deltacards.dsl.api import *


@card(367)
class Mine(Spell):
    turbo = (
        SELF.erase()
        >> YOU.hit(2)
        >> YOU.draw_next()
    )


@card(371)
class Spade(Spell):
    targets = ENEMY_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)

    magic = TARGET.hit(3).store_result(hit_result).to(
        Check(hit_result.killed).to(
            ((ENEMY_MONSTERS & ~TARGET) >> RANDOM(1)).hit(3)
        )
    )


@card(376)
class PuzzleBox(Spell):
    magic = (ENEMY_MONSTERS & (TEMPLATE_NAME == "Rouxls Kaard")).silence()


@card(379)
class Crown(Spell):
    targets = ALL_MONSTERS

    magic = (
        Check(TARGET & (TEMPLATE_NAME == "C-Round")).to(
            TARGET.turn_into(GENERATE_CARD("K-Round")),
            else_=TARGET.buff(attack=+1, hp=+2)
        )
        >> YOU.draw_next()
    )


@card(488)
class Spying(Spell):
    magic = YOU.choose(OPPONENT_HAND).to(
        CHOICE_SELECTED.buff(cost=+1)
    )


@card(516)
class BreakingLove(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.buff(attack=-1, hp=-1)
        >> YOU.draw_next()
    )


@card(535)
class CreateAMachine(Spell):
    magic = YOU.choose(
        (
            CARD_LIBRARY
            & HAS_TRIBE(Tribe.THRASHING_PART)
        ) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(585)
class BrokenKey(Spell):
    magic = (
        GENERATE_CARD("Cell Key").to_deck()
        >> YOU.draw_next()
    )


@card(586)
class CellKey(Monster):
    magic = YOU.choose(
        (
            CARD_LIBRARY
            & HAS_TRIBE(Tribe.CHAOS_WEAPON)
        ) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.buff(cost=-2)
        >> CHOICE_SELECTED.to_hand()
    )


@card(622)
class Mauswheel(Monster):
    generated_card: Var[Card] = Var(Card)
    bonus: Var[int] = Var(int)

    magic = (
        SetVar(
            var=bonus,
            value=LEAST(
                COUNT((
                    GOLD_SPENT(player=YOU, scope=THIS_TURN, reason='play_monster')
                    | GOLD_SPENT(player=YOU, scope=THIS_TURN, reason='play_spell')
                ) & (CARD_ID != SELF.id)),
                3
            )
        )
        >> For(
            3,
            (
                SetVar(var=generated_card, value=GENERATE_CARD("Maus"))
                >> generated_card.add_keyword(HASTE)
                >> generated_card.buff(attack=bonus, hp=bonus)
                >> generated_card.summon()
            )
        )
    )


@card(623)
class Cursor(Monster):
    magic = YOU.draw_next()


@card(627)
class CyberCage(Monster):
    released_card: Var[Card] = Var(Card)

    dust = Check(TURN_PLAYER.id == OPPONENT.id).to(
        SELF.release_caught_card(var=released_card).to(
            released_card.summon(controller=released_card.controller)
        )
    )


@card(631)
class Shovel(Monster):
    magic = Check(LOOP_COPY & HAND & ~HAS_STATUS(LOOP)).to(
        Program(3).to(
            LOOP_COPY.erase().to(
                SELF.buff(attack=+3, hp=+4)
            )
        )
    )


@card(643)
class PrisonBars(Spell):
    targets = ENEMY_MONSTERS

    magic = (
        TARGET.paralyze()
        >> (ENEMIES & ~TARGET).hit(1)
    )


@card(648)
class SpamtonPainting(Monster):
    generated_card: Var[Card] = Var(Card)

    turn_end = (ALLY_MONSTERS & ~SELF).add_keyword(TAUNT)

    support = (
        SetVar(var=generated_card, value=GENERATE_CARD("Queen Painting"))
        >> generated_card.set_base_stats(
            cost=SELF.base.cost,
            attack=SELF.base.attack,
            hp=SELF.base.hp
        )
        >> SELF.turn_into(generated_card)
    )


@card(665)
class HyperlinkBlocked(Spell):
    magic = (
        YOU.hit(1)
        >> YOU.draw((DECK & (TEMPLATE_ID != SELF.template_id)).first())
    )


@card(668)
class Zephyr(Spell):
    targets = ENEMY_MONSTERS

    hit_result: Var[StepResult] = Var(StepResult)

    magic = TARGET.hit(5).store_result(hit_result).to(
        Check(hit_result.excess_damage > 0).to(
            ((ENEMY_MONSTERS & ~TARGET) >> RANDOM(1)).hit(hit_result.excess_damage)
        )
    )


@card(670)
class DancingStickman(Monster):
    targets = ALL_MONSTERS

    magic = (
        TARGET.add_keyword(TAUNT)
        >> YOU.buff(hp=+3)
    )


@card(672)
class FeatherStorm(Monster):
    targets = ALLIES | ENEMIES

    magic = (
        TARGET.hit(2)
        >> ENEMIES.hit(1)
    )


@card(677)
class SansMilk(Spell):
    targets = ALL_MONSTERS

    magic = TARGET.set_status(
        DODGE,
        value=TARGET.status(DODGE) + 1
    )


@card(696)
class FinalGambit(Spell):
    magic = (
        GENERATE_CARD("Ultimathrash").summon()
        >> YOU.earn_gold(7)
        >> ENEMIES.hit(7)
        >> ALLIES.heal(7)
        >> (GENERATE_CARD("Draft").to_hand() * 7)
    )


@card(701)
class Vase(Monster):
    dust = Check(TURN_PLAYER.id == OPPONENT.id).to(
        Check(KILLER & IS_MONSTER).to(
            KILLER.buff(attack=-1, hp=-1)
        )
    )


@card(708)
class BlueHouse(Monster):
    generated_card: Var[Card] = Var(Card)

    _enemy_red_houses = ENEMY_MONSTERS & (TEMPLATE_NAME == "Red House")

    dust = Check(_enemy_red_houses).to(
        (
            SetVar(var=generated_card, value=_enemy_red_houses >> RANDOM(1))
            >> generated_card.silence()
            >> generated_card.kill()
        ),
        else_=GENERATE_CARD("Red House").summon()
    )


@card(709)
class RedHouse(Monster):
    dust = YOU.heal(2)


@card(711)
class Snowgrave(Spell):
    targets = ALL_MONSTERS

    target_attack: Var[int] = Var(int)
    target_hp: Var[int] = Var(int)
    generated_card: Var[Card] = Var(Card)

    magic = Check(
        COUNT(SPELLS_CAST(player=YOU) & (TEMPLATE_ID == SELF.template_id)) == 0
    ).to(
        SetVar(var=target_attack, value=TARGET.attack)
        >> SetVar(var=target_hp, value=TARGET.hp)
        >> TARGET.silence()
        >> TARGET.kill()
        >> For(
            EMPTY_SLOTS(HAND),
            (
                SetVar(var=generated_card, value=GENERATE_CARD("Ice Crystal"))
                >> generated_card.set_stats(attack=target_attack, hp=target_hp)
                >> generated_card.to_hand()
            )
        )
    )


@card(712)
class IceCrystal(Monster):
    targets = ALL_MONSTERS

    magic = TARGET.paralyze()

    dust = ENEMY_MONSTERS.hit(3)


@card(718)
class BigShot(Spell):
    magic = ALLIES.hit(99) * 99


@card(719)
class IrresistibleDeal(Spell):
    magic = (
        YOU.choose(
            (
                CARD_LIBRARY
                & IS_SPELL
                & HAS_TRIBE(Tribe.BARGAIN)
            ) >> GENERATE_CARD()
        ).to(
            Cast(
                card=CHOICE_SELECTED,
                controller=YOU
            )
        )
        >> YOU.artifact("FREE KROMER").update_artifact_counter(-6)
    )


@card(724)
class MsPipis(Monster):
    turn_start = SELF.kill().to(
        (HAND & IS_MONSTER).buff(
            attack=-2,
            hp=-2,
            min_attack=1,
            min_hp=1
        )
        >> (BOARD & IS_MONSTER).buff(attack=-2, hp=-2)
    )


@card(725)
class ShadowCrystal(Spell):
    generated_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (
            CARD_LIBRARY
            & IS_MONSTER
            & (RARITY == LEGENDARY)
            & (TEMPLATE_NAME != "Seam")
        ) >> GENERATE_CARD()
    ).to(
        SetVar(var=generated_card, value=CHOICE_SELECTED)
        >> SELF.schedule_delay_effect()
    )

    delay = generated_card.to_hand()


@card(736)
class PoliceLine(Monster):
    turn_end = (
        SELF.silence()
        >> SELF.add_keyword(TAUNT)
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

        return GENERATE_CARD("Police Line").summon()


@card(739)
class PetrifiedMonster(Monster):
    dust = ALLIES.hit(2)

    turn_end = SELF.kill()


@card(783)
class Chalk(Spell):
    magic = (
        OPPONENT.hit(5)
        >> YOU.draw_next()
        >> SELF.schedule_delay_effect()
    )

    delay = ALLY_MONSTERS.buff(attack=+1, hp=+1)


@card(789)
class ChaosBomb(Spell):
    magic = Cast(
        card=(
            CARD_LIBRARY
            & IS_SPELL
            & HAS_TRIBE(Tribe.CHAOS_WEAPON)
            & (TEMPLATE_NAME != "Club Chaos")
        ) >> GENERATE_CARD(),
        controller=YOU
    )


@card(795)
class DetachableHands(Spell):
    magic = (
        (
            CARD_LIBRARY
            & HAS_TRIBE(Tribe.GIGA_ATTACK)
        ) >> GENERATE_CARD()
    ).to_hand()


@card(800)
class GIGABaseball(Monster):
    turn_start = SELF.kill().to(
        ALLIES.heal(3)
        >> ENEMIES.hit(2)
    )


@card(886)
class Sharpshoot(Spell):
    targets = ALL_MONSTERS

    magic = (
        TARGET.add_keyword(TAUNT)
        >> TARGET.add_keyword(WANTED)
    )


@card(891)
class GrandPrize(Monster):
    released_card: Var[Card] = Var(Card)
    your_copy: Var[Card] = Var(Card)
    enemy_copy: Var[Card] = Var(Card)

    dust = SELF.release_caught_card(var=released_card).to(
        SetVar(var=your_copy, value=released_card >> COPY(controller=YOU))
        >> SetVar(var=enemy_copy, value=released_card >> COPY(controller=OPPONENT))
        >> your_copy.buff(cost=-1)
        >> your_copy.to_hand()
        >> enemy_copy.to_hand(controller=OPPONENT)
    )


def _gacha_ball_choice(rarity: CardRarity, gachapon):
    return YOU.choose(
        (
            CARD_LIBRARY
            & (RARITY == rarity)
        ) >> RANDOM(4) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.to_hand()
        >> gachapon.update_artifact_counter(+1)
    )


@card(900)
class GachaBall(Spell):
    _gachapon = YOU.artifact("Gachapon")

    magic = Check(YOU & HAS_ARTIFACT("Gachapon")).to(
        Check(_gachapon.active).to(
            Check(_gachapon.counter % 4 == 0).to(
                _gacha_ball_choice(COMMON, _gachapon),
                else_=Check(_gachapon.counter % 4 == 1).to(
                    _gacha_ball_choice(RARE, _gachapon),
                    else_=Check(_gachapon.counter % 4 == 2).to(
                        _gacha_ball_choice(EPIC, _gachapon),
                        else_=_gacha_ball_choice(LEGENDARY, _gachapon)
                    )
                )
            )
        )
    )


@card(916)
class FoodStack(Spell):
    magic = (LOOP_COPY & HAND).erase().to(
        For(
            SELF.status(LOOP),
            (ENEMY_MONSTERS >> RANDOM(1)).hit(3)
        )
    )


@card(918)
class RockChord(Spell):
    magic = GENERATE_CARD("Rock").summon()


@card(920)
class Susiezilla(Monster):
    magic = SELF.force_attack(ENEMY_MONSTERS)

    def iter_modifiers(self, game):
        if self.zone is not CardZone.HAND:
            return

        played_count = sum(
            1
            for res in game.log_by_type[CardPlayedResult]
            if (
                res.player_id == self.controller_id
                and res.card.template.id == self.template.id
            )
        )

        if played_count <= 0:
            return

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="In your hand, this has +3 COST for each Susiezilla you played this game",
            applies=lambda q: q.card is self,
            apply=lambda cost, q: cost + (3 * played_count),
        )


@card(928)
class C1225(Monster):
    turn_end = OPPONENT_HAND.erase()


@card(930)
class LaserPointere(Spell):
    targets = ENEMY_MONSTERS

    attacker: Var[TargetSelector] = Var(TargetSelector)

    magic = ForEach(
        ADJACENT(TARGET),
        var=attacker,
        effect=attacker.force_attack(TARGET)
    )


@card(936)
class BlackKnife(Spell):
    damage_not_dealt: Var[int] = Var(int, default=0)

    turbo = (
        SELF.erase()
        >> YOU.draw_next()
        >> For(
            6,
            effect=Check(COUNT(ALLY_MONSTERS) > 0).to(
                (ALLY_MONSTERS >> RANDOM(1)).hit(1),
                else_=SetVar(
                    var=damage_not_dealt,
                    value=damage_not_dealt + 1
                )
            )
        )
        >> Check(damage_not_dealt > 0).to(
            YOU.hit(damage_not_dealt)
        )
    )


@card(969)
class MewMewMagic(Spell):
    _pink_on_board = EXISTS(
        ALLY_MONSTERS
        & (TEMPLATE_NAME == "Pink")
    )

    targets = (
        ALLY_MONSTERS
        | (
            ENEMY_MONSTERS
            & _pink_on_board
        )
    )

    attack_before: Var[int] = Var(int)
    hp_before: Var[int] = Var(int)
    reduced_stats: Var[int] = Var(int)

    _doki_meter = YOU.artifact("Doki-Meter!")

    _complete_doki = Check(
        _doki_meter.counter >= 15
    ).to(
        GENERATE_CARD("Pink's Ghost").summon()
        >> GENERATE_CARD("Pink").to_deck()
        >> _doki_meter.update_artifact_counter(-15)
    )

    _progress_doki = Check(_doki_meter.active).to(
        _doki_meter.update_artifact_counter(
            LEAST(
                reduced_stats,
                GREATEST(
                    0,
                    15 - _doki_meter.counter,
                ),
            )
        )
        >> _complete_doki,
        else_=NO_EFFECT,
    )

    magic = (
        SetVar(
            var=attack_before,
            value=TARGET.attack
        )
        >> SetVar(
            var=hp_before,
            value=TARGET.hp
        )
        >> TARGET.halve_stats(round_up=True).to(  # Mew Mew Magic halves stats rounded up
            SetVar(
                var=reduced_stats,
                value=GREATEST(
                    0,
                    (attack_before - TARGET.attack)
                    + (hp_before - TARGET.hp)
                )
            )
            >> Check(
                YOU & HAS_ARTIFACT("Doki-Meter!")
            ).to(_progress_doki)
        )
    )


@card(978)
class PinksGhost(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker.id != self.id:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        halve_stats = defender.actions.halve_stats(round_up=False)

        if defender.template.rarity is CardRarity.DETERMINATION:
            return halve_stats

        return halve_stats.to(
            (
                RESOLVE_ENTITY(res.defender_id)
                >> EXACT_COPY()
            ).to_hand()
        )


@card(983)
class OurOMEGA(Spell):
    chosen_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        (
            CARD_BY_NAME("Aqua")
            | CARD_BY_NAME("Seth")
            | CARD_BY_NAME("Green")
            | CARD_BY_NAME("Yellow")
            | CARD_BY_NAME("Blue")
            | CARD_BY_NAME("Orange")
        ) >> GENERATE_CARD()
    ).to(
        SetVar(var=chosen_card, value=CHOICE_SELECTED)
        >> chosen_card.to_hand()
        >> SELF.schedule_delay_effect()
    )

    delay = (chosen_card & HAND).to_deck()
