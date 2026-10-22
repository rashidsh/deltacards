from deltacards.dsl.api import *


AMALGAMATE = HAS_TRIBE(Tribe.AMALGAMATE)
DOG = HAS_TRIBE(Tribe.DOG)
FROGGIT = HAS_TRIBE(Tribe.FROGGIT)
MOLD = HAS_TRIBE(Tribe.MOLD)


@card(32)
class MemoryHead(Monster):
    magic = LOOP_COPY.set_stats(cost=2, attack=3, hp=3)


@card(33)
class Endogeny(Monster):
    targets = HAND & (DOG | AMALGAMATE)

    magic = (
        Check(TARGET & DOG).to(
            TARGET.buff(attack=+1)
            >> TARGET.add_keyword(HASTE)
        )
        >> Check(TARGET & AMALGAMATE).to(
            TARGET.buff(hp=+1)
            >> TARGET.add_keyword(TAUNT)
        )
    )


@card(34)
class ReaperBird(Monster):
    draw_result: Var[StepResult] = Var(StepResult)

    magic = (
        YOU.draw(
            ((DECK & (AMALGAMATE | FROGGIT)) >> MAX(COST)).first()
        ).store_result(draw_result).to(
            Check(SYNERGY_TRIGGERED).to(
                Buff(target=draw_result.card_id, attack=+2, hp=+1)
            )
        )
    )

    synergy = NO_EFFECT


@card(35)
class LemonBread(Monster):
    played_count: Var[int] = Var(int)
    enemy_monster: Var[Monster] = Var(Monster)

    magic = (
        SetVar(
            var=played_count,
            value=COUNT(
                CARDS_PLAYED(player=YOU, scope=THIS_TURN)
                & IS_MONSTER
                & (MOLD | AMALGAMATE)
            ) + 1
        )
        >> ForEach(
            ENEMY_MONSTERS,
            var=enemy_monster,
            effect=enemy_monster.set_status(
                MOLD_SPORE,
                value=enemy_monster.status(MOLD_SPORE) + played_count
            )
        )
    )


@card(109)
class Everyman(Monster):
    targets = ALLY_MONSTERS & AMALGAMATE & (TEMPLATE_ID != SELF.template_id)

    copied_card: Var[Card] = Var(Card)

    magic = (
        TARGET.buff(attack=+1, hp=+1)
        >> SetVar(var=copied_card, value=TARGET >> COPY())
        >> copied_card.to_hand()
        >> Check(SYNERGY_TRIGGERED).to(
            (TARGET | copied_card).buff(attack=+1, hp=+1)
        )
    )

    synergy = NO_EFFECT


@card(241)
class Eye(Monster):
    copied_card: Var[TargetSelector] = Var(TargetSelector)

    magic = YOU.choose(
        ((DECK & AMALGAMATE & (TEMPLATE_ID != SELF.template_id)) >> DISTINCT(TEMPLATE_ID))[:3],
    ).to(
        SetVar(var=copied_card, value=CHOICE_SELECTED >> COPY())
        >> copied_card.buff(attack=+1, hp=+1)
        >> copied_card.to_deck(pos='top')
    )


@card(762)
class WatchingMan(Monster):
    magic = (ALLY_MONSTERS & ~SELF).heal(2)

    synergy = (ALLY_MONSTERS & ~SELF).buff(hp=+2)


@card(899)
class Friendogeny(Monster):
    magic = (
        YOU.draw_next()
        >> Check(SELF.buffs.attack > 0).to(
            YOU.draw_next()
        )
        >> Check(SELF.buffs.max_hp > 0).to(
            SELF.add_keyword(DARKSPAWN)
        )
    )
