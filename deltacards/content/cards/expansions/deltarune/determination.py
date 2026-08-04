from deltacards.dsl.api import *


@card(263)
class Kris(Monster):
    drawn_monster: Var[Card] = Var(Card)

    turn_end = (
        SetVar(var=drawn_monster, value=(DECK & IS_MONSTER).first())
        >> YOU.draw(drawn_monster).to(
            drawn_monster.buff(
                attack=SELF.buffs.attack,
                hp=SELF.buffs.max_hp
            )
        )
    )

    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return defender.actions.silence()

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        return SELF.buff(attack=+1, hp=+1)


@card(505)
class SoullessKris(Monster):
    magic = YOU.add_artifact(
        ARTIFACT_BY_NAME("Dark Fountain")
    ).to(
        YOU.artifact("Dark Fountain").update_artifact_counter(
            COUNT_DISTINCT(
                CARDS_PLAYED(player=YOU) & NON_TOKEN,
                TEMPLATE_ID
            )
        )
    )


@card(518)
class TheVessel(Monster):
    copied_card: Var[Card] = Var(Card)

    _last_card_played = (
        (
            CARDS_PLAYED(player=YOU)
            & NON_TOKEN
            & (TEMPLATE_ID != SELF.template_id)
        ).last()
        >> AS_CARDS()
    )

    magic = (
        SELF.turn_into(GENERATE_CARD("True Vessel"))
        >> Check(SELF & HAS_STATUS(LOOP)).to(
            (
                (LOOP_COPY & HAND).to_deck()
                >> SetVar(var=copied_card, value=_last_card_played >> COPY())
                >> Check(copied_card & IS_MONSTER).to(
                    copied_card.set_stats(hp=GREATEST(copied_card.hp, 1))
                )
            ),
            else_=SetVar(var=copied_card, value=_last_card_played >> EXACT_COPY())
        )
        >> copied_card.to_hand()
    )


@card(717)
class SpamtonNEO(Monster):
    magic = OPPONENT.add_artifact(ARTIFACT_BY_NAME("FREE KROMER"))


@card(794)
class GIGAQueen(Monster):
    magic = (
        YOU.choose(
            (
                CARD_LIBRARY
                & HAS_TRIBE(Tribe.GIGA_ATTACK)
                & ~HAS_TRIBE(Tribe.ALL)
                & ~IN_HISTORY(SPELLS_CAST(player=YOU))
            ) >> GENERATE_CARD()
        ).to(
            CHOICE_SELECTED.to_hand()
        )
        >> YOU.add_artifact(ARTIFACT_BY_NAME("Imminent Showdown"))
    )


@card(901)
class Titan(Monster):
    magic = YOU.add_artifact(ARTIFACT_BY_NAME("Constricting Darkness"))


@card(935)
class RoaringKnight(Monster):
    damage_not_dealt: Var[int] = Var(int, default=0)
    hit_result: Var[StepResult] = Var(StepResult)
    monster: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        OPPONENT.hit(12)
        >> ForEach(
            ENEMY_MONSTERS,
            var=monster,
            effect=(
                monster.hit(12).store_result(hit_result).to(
                    SetVar(
                        var=damage_not_dealt,
                        value=damage_not_dealt + hit_result.excess_damage
                    ),
                    else_=SetVar(
                        var=damage_not_dealt,
                        value=damage_not_dealt + 12
                    )
                )
            )
        )
        >> Check((damage_not_dealt // 10) > 0).to(
            GENERATE_CARD("Black Knife", controller=OPPONENT).to_deck(
                controller=OPPONENT,
                pos=RANGE(1, COUNT(DECK) + 1) >> RANDOM(1)
            ) * (damage_not_dealt // 10)
        )
    )


@card(955)
class HammerOfJustice(Monster):
    targets = ALLY_MONSTERS

    magic = (
        TARGET.buff(attack=+3, hp=+3)
        >> TARGET.add_keyword(HASTE)
        >> SLOT_OF(TARGET).enchant(
            ENCHANTMENT_BY_NAME('gersons-hammer')
        )
    )


@card(977)
class Pink(Monster):
    game_start = YOU.add_artifact(
        ARTIFACT_BY_NAME("Doki-Meter!")
    )


@card(986)
class Flowery(Monster):
    game_start = YOU.add_artifact(
        ARTIFACT_BY_NAME("Power of Friendship")
    )

    magic = GENERATE_CARD("Our OMEGA").to_hand()

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if not res.defender_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return GENERATE_CARD("Our OMEGA").to_hand()
