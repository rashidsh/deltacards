from deltacards.dsl.api import *


@card(350)
class Doodlebog(Monster):
    magic = Switch(
        left=SELF.buff(hp=+2),
        right=SELF.buff(attack=+2)
    )


@card(351)
class GasterBlaster(Spell):
    targets = ALL_MONSTERS | YOU

    magic = TARGET.hit(8)


@card(353)
class LeftTentacle(Monster):
    dust = OPPONENT.hit(2)


@card(354)
class RightTentacle(Monster):
    dust = YOU.heal(3)


@card(357)
class Bun(Monster):
    dust = (ALLY_MONSTERS & (TEMPLATE_NAME == "Bunbun")).buff(attack=+3)


@card(358)
class Load(Spell):
    # TODO
    ...


@card(366)
class LittleMine(Spell):
    turbo = YOU.hit(3) >> YOU.draw_next()


@card(368)
class BigMine(Spell):
    turbo = YOU.hit(5) >> YOU.draw_next()


@card(369)
class Thundersnail(Spell):
    dustpile_cards: Var[TargetSelector] = Var(TargetSelector)
    copied_cards: Var[TargetSelector] = Var(TargetSelector)

    magic = (
        SetVar(
            var=dustpile_cards,
            value=(
                (
                    DUSTPILE
                    & HAS_TRIBE(Tribe.SNAIL)
                    & (COST == 1)
                ) >> DISTINCT(TEMPLATE_ID)
            )[:4],
        )
        >> SetVar(var=copied_cards, value=dustpile_cards >> COPY())
        >> dustpile_cards.erase()
        >> copied_cards.summon()
        >> (copied_cards & BOARD).trigger_ability(MAGIC)
        >> (copied_cards & BOARD).add_keyword(HASTE)
        >> (copied_cards & BOARD).set_status(DODGE, value=1)
    )


@card(398)
class Scope(Spell):
    magic = YOU.choose(
        DECK >> RANDOM(2)
    ).to(
        YOU.draw(CHOICE_SELECTED)
    )


@card(428)
class Eggs(Monster):
    magic = Check(
        (COUNT(DUSTPILE & (TEMPLATE_NAME == "Flour")) >= 1)
        & (COUNT(DUSTPILE & (TEMPLATE_NAME == "Milk")) >= 1)
    ).to(
        (DUSTPILE & (TEMPLATE_NAME == "Flour")).first().erase()
        >> (DUSTPILE & (TEMPLATE_NAME == "Milk")).first().erase()
        >> SELF.turn_into(GENERATE_CARD("Cake"))
    )


@card(429)
class Flour(Monster):
    magic = Check(
        (COUNT(DUSTPILE & (TEMPLATE_NAME == "Eggs")) >= 1)
        & (COUNT(DUSTPILE & (TEMPLATE_NAME == "Milk")) >= 1)
    ).to(
        (DUSTPILE & (TEMPLATE_NAME == "Eggs")).first().erase()
        >> (DUSTPILE & (TEMPLATE_NAME == "Milk")).first().erase()
        >> SELF.turn_into(GENERATE_CARD("Cake"))
    )


@card(430)
class Milk(Monster):
    magic = Check(
        (COUNT(DUSTPILE & (TEMPLATE_NAME == "Eggs")) >= 1)
        & (COUNT(DUSTPILE & (TEMPLATE_NAME == "Flour")) >= 1)
    ).to(
        (DUSTPILE & (TEMPLATE_NAME == "Eggs")).first().erase()
        >> (DUSTPILE & (TEMPLATE_NAME == "Flour")).first().erase()
        >> SELF.turn_into(GENERATE_CARD("Cake"))
    )


@card(431)
class Cake(Monster):
    dust = ALLIES.heal(5)


@card(461)
class InstantNoodles(Spell):
    magic = (HAND & IS_MONSTER).buff(attack=+1, hp=+1)

    def iter_modifiers(self, game):
        if self.zone is not CardZone.HAND:
            return

        controller = game.player(self.controller_id)
        opponent = controller.opponent

        monster_count = sum(
            1
            for card_ in (*controller.dustpile.cards, *opponent.dustpile.cards)
            if isinstance(card_, Monster)
        )

        yield IntModifier(
            kind=ModKind.COST,
            layer=CostLayer.ADD,
            source=self,
            description="In your hand, this has -1 COST for each monster in both players' dustpiles",
            applies=lambda q: q.card is self,
            apply=lambda cost, q: cost - monster_count,
        )


@card(511)
class TeaSet(Spell):
    targets = ALL_PLAYERS | ALL_MONSTERS

    magic = (
        TARGET.heal(4)
        >> Check(TARGET & IS_MONSTER).to(
            TARGET.buff(attack=+1, hp=+1)
        )
    )


@card(513)
class DynamiteStick(Monster):
    dust = (ENEMY_MONSTERS >> RANDOM(1)).hit(1)


@card(522)
class BrokenPillar(Monster):
    targets = ALLY_MONSTERS

    magic = TARGET.buff(attack=+1, hp=+2)


@card(536)
class Dream(Spell):
    targets = HAND

    magic = (
        TARGET.buff(cost=-1)
        >> TARGET.to_deck()
        >> (YOU.draw((DECK & ~TARGET).first()) * 2)
    )


@card(537)
class RealKnife(Spell):
    targets = ENEMY_MONSTERS

    magic = (
        TARGET.kill()
        >> YOU.artifact("Genocide").update_artifact_counter(+1)
        >> YOU.buff(hp=-YOU.artifact("Genocide").counter)
    )


@card(540)
class PileOfBones(Monster):
    targets = HAND & HAS_TRIBE(Tribe.DOG)

    magic = TARGET.buff(attack=+3, hp=+3)


@card(544)
class PopatoChisps(Spell):
    targets = ALL_MONSTERS & NON_DT & HAS_ANY_TRIBE

    copied_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=copied_card, value=TARGET >> COPY())
        >> copied_card.buff(attack=+1, hp=+1)
        >> copied_card.to_hand()
    )


@card(569)
class Bone(Monster):
    @on_event(DodgeConsumedResult)
    def on_dodge_consumed(self, res: DodgeConsumedResult, game, **kwargs):
        if res.monster.id != self.id:
            return None

        return ((OPPONENT_HAND & IS_MONSTER) >> RANDOM(2)).buff(attack=+1, hp=+1)


@card(575)
class TimeWarp(Spell):
    magic = ((HAND | DECK) & GENERATED).buff(cost=-1)


@card(576)
class Shield(Spell):
    targets = ALLY_MONSTERS

    magic = TARGET.buff(attack=+1, hp=+1) >> YOU.draw_next()


@card(577)
class Draft(Spell):
    magic = YOU.choose(
        DISCOVER(
            IS_MONSTER,
            RARITY <= EPIC,
            COST >= 5,
            COST <= 6,
            n=5,
        )
    ).to(
        CHOICE_SELECTED.buff(cost=-1)
        >> CHOICE_SELECTED.to_hand()
    )


@card(578)
class CrystalShard(Spell):
    targets = ALLIES | ENEMIES

    magic = TARGET.hit(3)


@card(596)
class Vegetables(Spell):
    turbo = SELF.erase() >> YOU.heal(2) >> YOU.draw_next()


@card(598)
class Gemstone(Spell):
    targets = ALLIES | ENEMIES

    magic = TARGET.hit(1)


@card(613)
class TotemicCarvings(Spell):
    magic = YOU.choose(
        DISCOVER(
            IS_MONSTER,
            NON_DT,
            NON_TOKEN,
            COST == 7,
            TEMPLATE_NAME != "Totem",
            n=7,
        )
    ).to(
        CHOICE_SELECTED.buff(cost=-7)
        >> CHOICE_SELECTED.to_hand()
    )


@card(614)
class ArcaneCodes(Spell):
    magic = Cast(
        card=(CARD_LIBRARY & IS_SPELL & NON_TOKEN) >> RANDOM(1) >> GENERATE_CARD(),
        controller=YOU,
        effect_target='random'
    )


@card(615)
class ToxicCloud(Monster):
    dust = Check(KILLER & IS_MONSTER).to(
        KILLER.add_keyword(KR)
        >> KILLER.buff(attack=-1, hp=-1)
    )


@card(706)
class Star(Monster):
    dust = YOU.heal(1)

    turn_end = SELF.kill()


@card(713)
class CrystalDownpour(Spell):
    generated_card: Var[Card] = Var(Card)

    magic = For(
        4,
        (
            SetVar(var=generated_card, value=GENERATE_CARD("Gemstone"))
            >> generated_card.set_stats(cost=0)
            >> generated_card.to_hand()
        )
    )


@card(750)
class MushroomDance(Spell):
    magic = YOU.choose(
        (
            CARD_LIBRARY
            & IS_SPELL
            & HAS_TRIBE(Tribe.DANCE)
        ) >> GENERATE_CARD()
    ).to(
        Cast(
            card=CHOICE_SELECTED,
            controller=YOU
        )
    )


@card(771)
class ACTButton(Spell):
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


@card(772)
class JunkForSale(Spell):
    magic = YOU.choose(
        DISCOVER(
            IS_MONSTER,
            RARITY <= EPIC,
            COST == 3,
            n=2,
        )
    ).to(
        CHOICE_SELECTED.set_stats(cost=0)
        >> CHOICE_SELECTED.to_hand()
        >> SELF.schedule_delay_effect()
    )

    delay = Check(
        ~EXISTS(HAND & (TEMPLATE_ID == SELF.template_id))
    ).to(
        GENERATE_CARD("Junk for Sale").to_hand()
    )
