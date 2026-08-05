from deltacards.dsl.api import *


@card(264)
class Ralsei(Monster):
    copied_card: Var[Card] = Var(Card)
    targets = HAND & IS_MONSTER & NON_DT

    magic = (
        SetVar(var=copied_card, value=TARGET >> COPY())
        >> copied_card.set_base_stats(attack=3, hp=3)
        >> copied_card.summon()
    )


@card(265)
class Lancer(Monster):
    generated_card: Var[Card] = Var(Card)

    magic = For(
        2,
        (
            SetVar(var=generated_card, value=GENERATE_CARD("Spade"))
            >> generated_card.buff(cost=-1)
            >> generated_card.to_hand()
        )
    )

    def iter_modifiers(self, game):
        if self.zone is not CardZone.BOARD:
            return

        yield IntModifier(
            kind=ModKind.DAMAGE,
            layer=DamageLayer.ADD,
            source=self,
            description="Enemy monsters take +2 DMG from spells",
            applies=lambda q: (
                isinstance(q.target, Monster)
                and q.target.controller_id != self.controller_id
                and q.kind is DamageKind.SPELL
            ),
            apply=lambda damage, q: damage + 2,
        )


@card(273)
class Noelle(Monster):
    need = COUNT_DISTINCT(
        GOLD_SPENT(player=YOU, reason='play_spell'),
        TEMPLATE_ID
    ) >= 4

    # should work for now
    magic = YOU.choose(
        (
            CARD_LIBRARY
            & IS_SPELL
            & (RARITY == EPIC)
        ) >> RANDOM(999) >> DISTINCT(CARD_SOUL) >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.buff(cost=-2)
        >> CHOICE_SELECTED.to_hand()
    )


@card(280)
class Susie(Monster):
    magic = (
        (ALLY_MONSTERS & ~SELF)
        | FRONT(SELF)
    ).set_stats(attack=3, hp=3)


@card(287)
class RouxlsKaard(Monster):
    magic = GENERATE_CARD("Puzzle Box", controller=OPPONENT).to_hand(controller=OPPONENT)


@card(419)
class SpadeKing(Monster):
    magic = Switch(
        left=ENEMY_MONSTERS.silence(),
        right=(ENEMY_MONSTERS & (HP <= 2)).kill()
    )


@card(444)
class Jevil(Monster):
    magic = YOU.choose(
        (
            CARD_LIBRARY
            & HAS_TRIBE(Tribe.CHAOS_WEAPON)
            & ~HAS_TRIBE(Tribe.ALL)
        ) >> GENERATE_CARD()
    ).to(
        Cast(
            card=CHOICE_SELECTED,
            controller=YOU
        )
    )


@card(472)
class Seam(Monster):
    need = COUNT(
        (DECK | DUSTPILE)
        & NON_GENERATED
        & IS_MONSTER
        & (RARITY == LEGENDARY)
    ) == 0

    magic = GENERATE_CARD("Shadow Crystal").to_hand() * 2


@card(504)
class BikerLancer(Monster):
    @on_event(AttackDeclaredResult)
    def on_attack_declared(self, res: AttackDeclaredResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Player):
            return None

        if defender.id != game.player(self.controller_id).opponent.id:
            return None

        return ((HAND & IS_MONSTER) >> RANDOM(2)).buff(attack=+1)


@card(508)
class HoodedRalsei(Monster):
    copied_card: Var[Card] = Var(Card)

    @on_event(SpellCastResult)
    def on_spell_cast(self, res: SpellCastResult, game, **kwargs):
        if res.player_id != self.controller_id:
            return None

        if res.card.is_generated:
            return None

        return (
            SetVar(var=self.copied_card, value=RESOLVE_ENTITY(res.card_id) >> COPY())
            >> self.copied_card.to_hand()
        )


@card(531)
class TeacherToriel(Monster):
    magic = YOU.choose(OPPONENT_HAND).to(
        CHOICE_SELECTED.to_deck()
    )


@card(664)
class Spamton(Monster):
    pipis_cards: Var[TargetSelector] = Var(TargetSelector)
    erased_count: Var[int] = Var(int)
    add_count: Var[int] = Var(int)
    not_added_count: Var[int] = Var(int)
    pipis: Var[Card] = Var(Card)

    magic = (
        SetVar(
            var=pipis_cards,
            value=DUSTPILE & IS_MONSTER & (TEMPLATE_NAME == "Pipis")
        )
        >> SetVar(var=erased_count, value=COUNT(pipis_cards))
        >> SetVar(var=add_count, value=LEAST(erased_count, EMPTY_SLOTS(HAND)))
        >> SetVar(var=not_added_count, value=GREATEST(erased_count - EMPTY_SLOTS(HAND), 0))
        >> pipis_cards.erase()
        >> For(
            add_count,
            (
                SetVar(var=pipis, value=GENERATE_CARD("Pipis"))
                >> pipis.add_keyword(HASTE)
                >> pipis.buff(attack=not_added_count, hp=not_added_count)
                >> pipis.to_hand()
            )
        )
    )


@card(675)
class Cyberdly(Monster):
    magic = SELF.buff(
        attack=COUNT_UNIQUE_TRIBES(DUSTPILE & IS_MONSTER),
        hp=COUNT_UNIQUE_TRIBES(DUSTPILE & IS_MONSTER)
    )

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if res.attacker_dead:
            return None

        return GENERATE_CARD("Feather Storm").to_hand() * 2


@card(697)
class Queen(Monster):
    targets = ENEMY_MONSTERS

    generated_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Werewire"))
        >> generated_card.summon().to(
            generated_card.catch(TARGET)
        )
    )


@card(707)
class CaptainRouxls(Monster):
    magic = (
        FillBoard(YOU, CARD_BY_NAME("Blue House"))
        >> FillBoard(OPPONENT, CARD_BY_NAME("Red House"))
        >> SELF.schedule_delay_effect()
    )

    delay = (ALL_MONSTERS & (TEMPLATE_NAME == "Blue House")).kill()


@card(710)
class Snoelle(Monster):
    targets = ALL_MONSTERS

    magic = (
        TARGET.paralyze()
        >> SELF.schedule_delay_effect()
    )

    delay = Check(TARGET.dead).to(
        Check(SELF & BOARD).to(
            SELF.set_base_stats(attack=SELF.base.attack + 1)
            >> Check(SELF.base.attack >= 5).to(
                SELF.erase().to(
                    GENERATE_CARD("Snowgrave").to_hand()
                ),
                else_=SELF.to_deck()
            )
        )
    )


@card(714)
class CagedJester(Monster):
    magic = YOU.add_artifact(
        ARTIFACT_BY_NAME("Freedom")
    ).to(
        YOU.artifact("Freedom").update_artifact_counter(
            COUNT_DISTINCT(
                SPELLS_CAST(player=YOU)
                & NON_TOKEN
                & ANOTHER_SOUL_THAN(YOU)
            )
        )
    )


@card(726)
class PlaceholderKris(Monster):
    support = ATTACKER.buff(attack=+2, hp=+2)


@card(760)
class ButlerRalsei(Monster):
    shock = YOU.buff(hp=+2)

    support = Program(1).to(
        ATTACKER.buff(hp=+2)
        >> SELF.trigger_ability(SHOCK)
    )


@card(780)
class Wheelvil(Monster):
    magic = For(
        (YOU.max_hp - YOU.hp) // 8,
        Cast(
            card=(
                CARD_LIBRARY
                & IS_SPELL
                & HAS_TRIBE(Tribe.CHAOS_WEAPON)
                & ~HAS_TRIBE(Tribe.ALL)
            ) >> RANDOM(1) >> GENERATE_CARD(),
            controller=YOU
        )
    )


@card(782)
class TeacherAlphys(Monster):
    need = (
        (COUNT(DUSTPILE & IS_MONSTER & (COST == 1)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 2)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 3)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 4)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 5)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 6)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 7)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 8)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 9)) >= 1)
        & (COUNT(DUSTPILE & IS_MONSTER & (COST == 10)) >= 1)
    )

    magic = (
        (DUSTPILE & IS_MONSTER & (COST == 1)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 2)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 3)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 4)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 5)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 6)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 7)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 8)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 9)).first()
        | (DUSTPILE & IS_MONSTER & (COST == 10)).first()
    ).erase().to(
        GENERATE_CARD("Chalk").to_deck() * 3
    )


@card(793)
class Swatch(Monster):
    generated_card: Var[Card] = Var(Card)

    turn_end = Check(SPENT_GOLD_ON_SPELLS_THIS_TURN >= 5).to(
        SetVar(var=generated_card, value=GENERATE_CARD("Swatch"))
        >> generated_card.set_base_stats(
            cost=generated_card.base.cost - 1,
            attack=generated_card.base.attack + 1,
            hp=generated_card.base.hp + 1,
        )
        >> generated_card.to_hand()
    )


@card(890)
class Tenna(Monster):
    chosen_monster: Var[Card] = Var(Card)
    generated_card: Var[Card] = Var(Card)

    magic = YOU.choose(
        OPPONENT_HAND & IS_MONSTER & NON_DT
    ).to(
        SetVar(var=chosen_monster, value=CHOICE_SELECTED)
        >> SELF.schedule_delay_effect()
    )

    delay = (
        SetVar(var=generated_card, value=GENERATE_CARD("Grand Prize"))
        >> generated_card.summon().to(
            generated_card.catch(chosen_monster)
        )
    )


@card(912)
class Jackenstein(Monster):
    magic = (
        YOU.add_artifact(ARTIFACT_BY_NAME("DARK ZONE"))
        >> OPPONENT.add_artifact(ARTIFACT_BY_NAME("DARK ZONE"))
        >> YOU.artifact("DARK ZONE").update_artifact_counter(-6)
    )


@card(926)
class Carol(Monster):
    targets = ENEMY_MONSTERS

    magic = (TARGET | ADJACENT(TARGET)).paralyze()


@card(929)
class ChefRouxls(Monster):
    magic = GENERATE_CARD("Laser Pointere").to_hand()


@card(965)
class Blue(Monster):
    need = (
        SPENT_GOLD_AMOUNT(
            player=YOU,
            scope=THIS_TURN,
            reason='play_monster'
        )
        + SPENT_GOLD_AMOUNT(
            player=YOU,
            scope=THIS_TURN,
            reason='play_spell'
        )
    ) >= 8

    magic = GENERATE_CARD("Blue Rose").summon() * 3


@card(970)
class Aqua(Monster):
    need = COUNT(
        CARDS_DRAWN(
            player=YOU,
            scope=THIS_TURN
        )
    ) >= 3

    magic = (
        ENEMIES.hit(1)
        >> YOU.draw_next()
    )


@card(979)
class Green(Monster):
    other_ally_monsters: Var[TargetSelector] = Var(TargetSelector)

    need = SUM(
        HEALING_DONE(controller=YOU),
        HEALED_AMOUNT
    ) >= 12

    magic = (
        SetVar(
            var=other_ally_monsters,
            value=ALLY_MONSTERS & ~SELF
        )
        >> other_ally_monsters.buff(attack=+1, hp=+1)
        >> other_ally_monsters.add_keyword(CANDY)
    )


@card(980)
class Seth(Monster):
    need = COUNT(
        ALL_MONSTERS & HAS_NEGATIVE_EFFECTS
    ) >= 3

    magic = ENEMY_MONSTERS.buff(attack=-2, hp=-2)


@card(981)
class Orange(Monster):
    ally_monsters: Var[TargetSelector] = Var(TargetSelector)

    need = COUNT(
        ATTACKS_DECLARED(
            attacker_controller=YOU,
            scope=THIS_TURN
        )
    ) >= 3

    magic = (
        SetVar(var=ally_monsters, value=ALLY_MONSTERS)
        >> ally_monsters.buff(attack=+1)
        >> ally_monsters.add_keyword(HASTE)
        >> ally_monsters.refresh_attacks()
    )


@card(982)
class Yellow(Monster):
    generated_card: Var[Card] = Var(Card)

    need = COUNT(
        MONSTERS_DIED(
            scope=THIS_TURN,
            killer_controller=YOU
        )
         & ~IS_COMBAT_KILL
    ) >= 2

    magic = (
        SetVar(var=generated_card, value=GENERATE_CARD("Quick Draw"))
        >> generated_card.set_status(LOOP, value=2)
        >> generated_card.to_hand()
    )
