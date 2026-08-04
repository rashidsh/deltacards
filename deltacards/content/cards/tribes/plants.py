from deltacards.dsl.api import *


PLANT = HAS_TRIBE(Tribe.PLANT)


@card(6)
class Vegetoid(Monster):
    turn_start = YOU.heal(5)


@card(26)
class Parsnik(Monster):
    paralyze_result: Var[StepResult] = Var(StepResult)

    targets = ALL_MONSTERS

    magic = (
        TARGET.paralyze().store_result(paralyze_result)
        >> Check(paralyze_result.success == False).to(
            TARGET.hit(2)
        )
    )


@card(36)
class SnowdrakesMom(Monster):
    summon_result: Var[StepResult] = Var(StepResult)

    magic = SELF.schedule_delay_effect()

    delay = GENERATE_CARD("Vegetoid").summon().store_result(summon_result).to(
        Check(SELF.buffs.attack > 0).to(
            Buff(target=summon_result.monster_id, attack=+1, hp=+1)
            >> AddKeyword(target=summon_result.monster_id, keyword=TRANSPARENCY)
        )
    )


@card(54)
class Flowey(Monster):
    generated_card: Var[Card] = Var(Card)

    dust = (
        SetVar(var=generated_card, value=GENERATE_CARD("Flowey"))
        >> generated_card.set_base_stats(
            cost=SELF.base.cost - 1,
            attack=SELF.base.attack - 1,
            hp=SELF.base.hp - 1,
        )
        >> generated_card.to_hand()
        >> Check(generated_card.base.attack <= 1).to(
            generated_card.turn_into(GENERATE_CARD("Demon Flowey"))
        )
    )


@card(105)
class EchoFlower(Monster):
    copied_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=copied_card, value=OPPONENT_HAND >> RANDOM(1) >> EXACT_COPY())
        >> copied_card.buff(cost=-1)
        >> copied_card.to_hand()
    )


@card(117)
class OmegaFlowey(Monster):
    # TODO
    ...


@card(124)
class GoldenFlowers(Monster):
    magic = YOU.choose(
        (
            (SPELLS_CAST(player=YOU) & NON_TOKEN)
            >> AS_TEMPLATES(distinct=True)
            >> RANDOM(3)
            >> GENERATE_CARD()
        )
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(136)
class Cactus(Monster):
    @on_event(EntityDamagedResult)
    def on_entity_damaged(self, res: EntityDamagedResult, game, **kwargs):
        if res.source_id != self.id:
            return None

        target = game.entity(res.target_id)
        if not isinstance(target, Monster):
            return None

        return target.actions.kill()


@card(188)
class BridgeSeed(Monster):
    magic = (
        YOU.draw_next()
        >> SELF.buff(hp=COUNT(ALLY_MONSTERS & (TEMPLATE_ID == SELF.template_id)))
    )


@card(228)
class Tree(Monster):
    magic = SELF.hit(2)

    synergy = ALLIES.heal(2)


@card(242)
class BurgerBush(Monster):
    turn_start = YOU.earn_gold(COUNT(ALLY_MONSTERS & PLANT))


@card(251)
class Ragel(Monster):
    generated_card: Var[Card] = Var(Card)

    synergy = (
        SetVar(var=generated_card, value=GENERATE_CARD("Mushroom Dance"))
        >> generated_card.to_hand()
        >> SELF.schedule_delay_effect()
    )

    delay = (generated_card & HAND).erase()


@card(278)
class DarkCandyTree(Monster):
    support = (
        ATTACKER.buff(hp=+1)
        >> Check(ATTACKER & PLANT).to(
            ATTACKER.buff(attack=+1)
        )
    )


@card(300)
class FlowerJar(Monster):
    released_card: Var[Card] = Var(Card)

    magic = Program(2).to(
        YOU.spend_gold(2).to(
            SELF.catch(GENERATE_CARD("Blue Rose")),
            else_=SELF.catch(GENERATE_CARD("Red Flower"))
        ),
        else_=SELF.catch(GENERATE_CARD("Green Clover"))
    )

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.summon(controller=released_card.controller)
    )


@card(303)
class RedBush(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        def other_ally_plant_count() -> int:
            return sum(
                1
                for monster in game.player(self.controller_id).board.cards
                if (
                    (monster is not self)
                    and monster.has_tribe(Tribe.PLANT)
                )
            )

        yield IntModifier(
            kind=ModKind.ATTACK,
            layer=StatLayer.ADD,
            source=self,
            description="+1 ATK for each other ally PLANT",
            applies=lambda q: q.monster is self,
            apply=lambda attack, q: attack + other_ally_plant_count(),
        )


@card(307)
class BloodyTree(Monster):
    turn_start = SELF.buff(attack=+1)


@card(308)
class DonationStump(Monster):
    magic = YOU.hit(2)

    synergy = OPPONENT.hit(2)


@card(317)
class FlowerCan(Monster):
    generated_card: Var[Card] = Var(Card)

    synergy = SELF.add_keyword(HASTE)

    dust = For(
        2,
        effect=(
            SetVar(var=generated_card, value=GENERATE_CARD("Green Clover"))
            >> generated_card.add_keyword(HASTE)
            >> generated_card.to_hand()
        )
    )


@card(392)
class GhostTree(Monster):
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_tribe(Tribe.PLANT):
            return None

        return SELF.buff(hp=+1)


@card(422)
class FlowerFingers(Monster):
    targets = ALL_PLAYERS | ALL_MONSTERS

    magic = TARGET.hit(COUNT(ALLY_MONSTERS & PLANT))


@card(424)
class ChristmasTree(Monster):
    magic = Check(~SYNERGY_TRIGGERED).to(
        GENERATE_CARD("Gift").summon() * 2
    )

    synergy = GENERATE_CARD("Gift").summon(attack=2, hp=2) * 2


@card(426)
class RabbickHole(Monster):
    dust = GENERATE_CARD("Rabbick").summon()


@card(435)
class FicusLicker(Monster):
    magic = YOU.draw((DECK & PLANT & (TEMPLATE_ID != SELF.template_id)).first())


@card(477)
class SpiderFlower(Monster):
    released_card: Var[Card] = Var(Card)

    magic = Switch(
        left=SELF.catch(GENERATE_CARD("Spider")),
        right=SELF.catch(GENERATE_CARD("Red Flower"))
    )

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.buff(cost=-1)
        >> released_card.to_hand(controller=released_card.controller)
    )


@card(489)
class WaterSausage(Monster):
    turbo = YOU.heal(3)


@card(519)
class Ficus(Monster):
    @on_event(MonsterKilledResult)
    def on_monster_killed(self, res: MonsterKilledResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_tribe(Tribe.PLANT):
            return None

        return SELF.buff(attack=+1)


@card(529)
class Vine(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.HAND:
            return

        def played_plant_count() -> int:
            return sum(
                1
                for res in game.log_by_type[CardPlayedResult]
                if res.player_id == self.controller_id
                and res.card.has_tribe(Tribe.PLANT)
            )

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="-1 COST for each PLANT you've played this game, max -9",
            applies=lambda q: q.card is self,
            apply=lambda cost, q: cost - min(played_plant_count(), 9)
        )


@card(550)
class DemonFlowey(Monster):
    generated_card: Var[Card] = Var(Card)

    dust = (
        SetVar(var=generated_card, value=GENERATE_CARD("Demon Flowey"))
        >> generated_card.set_base_stats(
            cost=generated_card.base.cost + 3,
            attack=generated_card.base.attack + 3,
            hp=generated_card.base.hp + 3,
        )
        >> generated_card.add_keyword(SILENCED)
        >> generated_card.add_keyword(HASTE)
        >> generated_card.to_deck()
    )


@card(751)
class RuinsTree(Monster):
    turn_end = YOU.heal(SELF.hp)


@card(813)
class SweetCorn(Monster):
    dust = KILLER.add_keyword(CANDY)


@card(844)
class GirlbossCactus(Monster):
    generated_card: Var[Card] = Var(Card)

    _effect = (
        SetVar(var=generated_card, value=GENERATE_CARD("Cactus"))
        >> generated_card.buff(hp=+2)
        >> generated_card.add_keyword(HASTE)
        >> generated_card.to_hand()
    )

    synergy = _effect
    dust = _effect


@card(933)
class MetaFlowey(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.PREVENT,
            source=self,
            description="Immune to DMG if there's a Flowey and this doesn't have Taunt",
            applies=lambda q: (
                q.target is self
                and not self.has_keyword(TAUNT)
                and any(
                    isinstance(monster, Monster)
                    and monster.template.name == "Flowey"
                    for monster in (
                        *game.player(self.controller_id).board.cards,
                        *game.player(self.controller_id).opponent.board.cards,
                    )
                )
            ),
            apply=lambda damage, q: 0,
        )

    magic = For(
        EMPTY_SLOTS(BOARD),
        effect=GENERATE_CARD("Flowey").summon()
    ) >> For(
        EMPTY_SLOTS(OPPONENT_BOARD),
        effect=GENERATE_CARD("Flowey", controller=OPPONENT).summon(controller=OPPONENT)
    )
