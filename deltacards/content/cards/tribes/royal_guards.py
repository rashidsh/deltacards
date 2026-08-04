from deltacards.dsl.api import *


ROYAL_GUARD = HAS_TRIBE(Tribe.ROYAL_GUARD)


@card(38)
class RoyalGuard1(Monster):
    dust = (ALLY_MONSTERS & ROYAL_GUARD).add_keyword(ARMOR)


@card(39)
class RoyalGuard2(Monster):
    dust = ((HAND & ROYAL_GUARD) >> RANDOM(4)).add_keyword(HASTE)


@card(62)
class Undyne(Monster):
    damage_not_dealt: Var[int] = Var(int, default=0)

    magic = For(
        10,
        effect=Check(COUNT(ENEMY_MONSTERS) > 0).to(
            (ENEMY_MONSTERS >> MIN(HP)).hit(1),
            else_=SetVar(
                var=damage_not_dealt,
                value=damage_not_dealt + 1
            )
        )
    ) >> Check(damage_not_dealt > 0).to(
        GENERATE_CARD("Spear").summon(
            attack=damage_not_dealt,
            hp=damage_not_dealt
        )
    )


@card(106)
class TheHeroine(Monster):
    magic = SELF.add_keyword(TAUNT)

    def on_would_die(self, entity: Entity, game, **kwargs):
        if entity.id != self.id:
            return None

        if self.base.hp <= 2:
            return None

        if len(game.player(self.controller_id).dustpile.cards) < 5:
            return None

        return [
            (DUSTPILE & IS_MONSTER)[:5].erase(),
            self.revive,
        ]

    def revive(self, ctx, **kwargs):
        base_attack = self.base.attack
        base_hp = self.base.hp

        self._reset()

        self.set_base_stats(attack=base_attack - 1, hp=base_hp - 2)


@card(315)
class RoyalGuard3(Monster):
    dust = (ALLY_MONSTERS & ROYAL_GUARD).add_keyword(CANDY)


@card(316)
class RoyalGuard4(Monster):
    X: Var[Card] = Var(Card)

    dust = ForEach(
        (ALLY_MONSTERS & ROYAL_GUARD),
        var=X,
        effect=X.set_status(
            DODGE,
            value=X.status(DODGE) + 1
        )
    )


@card(716)
class RoyalPapyrus(Monster):
    need = COUNT(
        DUSTPILE
        & IS_MONSTER
        & NON_GENERATED
        & (COST >= 9)
    ) >= 10

    magic = YOU.add_artifact(
        ARTIFACT_BY_NAME("Underground Army")
    )


@card(742)
class CasualGuard1(Monster):
    draw_result: Var[StepResult] = Var(StepResult)

    magic = (
        YOU.draw(
            (DECK & ROYAL_GUARD & HAS_ABILITY(DUST)).first()
        ).store_result(draw_result).to(
            TriggerAbility(target=draw_result.card_id, ability=DUST)
            >> Check(COUNT(ALLY_MONSTERS) == 1).to(
                SELF.add_keyword(HASTE)
            )
        )
    )


@card(743)
class CasualGuard2(Monster):
    def iter_modifiers(self, game):
        if self.zone is not CardZone.HAND:
            return

        def played_high_cost_card_this_turn() -> bool:
            return any(
                res.player_id == self.controller_id
                and res.turn == game.turn
                and res.turn_player_id == game.turn_player.id
                and res.card.base.cost >= 9
                for res in game.log_by_type[CardPlayedResult]
            )

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="-3 COST if you played a card with a base COST of 9+ GOLD this turn.",
            applies=lambda q: q.card is self and played_high_cost_card_this_turn(),
            apply=lambda cost, q: cost - 3,
        )


@card(838)
class ZenithMartlet(Monster):
    magic = (
        (
            DUSTPILE
            & IS_MONSTER
            & NON_TOKEN
            & (COST <= 9)
        )
        >> LIMIT_PER(TEMPLATE_ID, 3)
    ).trigger_ability(DUST)


@card(880)
class Martlet(Monster):
    magic = Switch(
        left=FRONT(SELF).hit(7),
        right=ENEMIES.hit(1) >> SELF.add_keyword(HASTE)
    )

    bullseye = Check(SELF & BOARD).to(
        SELF.set_base_stats(cost=SELF.base.cost - 1)
        >> SELF.to_hand()
    )
