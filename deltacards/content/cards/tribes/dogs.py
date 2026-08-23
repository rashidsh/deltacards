from deltacards.dsl.api import *


DOG = HAS_TRIBE(Tribe.DOG)


@card(40)
class AnnoyingDog(Monster):
    magic = SELF.schedule_delay_effect()

    delay = (
        GENERATE_CARD("Dog Residue").to_hand()
        >> Check(SELF.buffs.attack > 0).to(
            GENERATE_CARD("Dog Residue").to_hand()
        )
    )


@card(43)
class LesserDog(Monster):
    dust = HAND.buff(cost=-1)


@card(45)
class Doggo(Monster):
    magic = SELF.schedule_delay_effect()

    delay = Check(SELF.buffs.attack > 0).to(
        FRONT(SELF).paralyze()
    )


@card(46)
class Dogamy(Monster):
    magic = Check(ALLY_MONSTERS & (TEMPLATE_NAME == "Dogaressa")).to(
        (HAND & DOG).buff(attack=+2, hp=+2)
    )


@card(47)
class Dogaressa(Monster):
    magic = Check(ALLY_MONSTERS & (TEMPLATE_NAME == "Dogamy")).to(
        SELF.buff(attack=+2, hp=+3)
        >> SELF.add_keyword(TAUNT)
        >> SELF.set_status(DODGE, value=SELF.status(DODGE) + 1)
    )


@card(48)
class GreaterDog(Monster):
    magic = Check(HAND & DOG).to(
        SELF.buff(hp=+3)
    )


@card(349)
class DogResidue(Monster):
    turn_end = Check(SELF.buffs.attack > 0).to(
        SELF.add_keyword(TAUNT)
    )


@card(442)
class SandDog(Monster):
    magic = (SELF >> EXACT_COPY()).summon()


@card(525)
class TooManyDogs(Monster):
    magic = Check(~EXISTS(HAND & (TEMPLATE_ID == SELF.template_id))).to(
        FillHand(YOU, CARD_BY_NAME("Dog Residue"))
    )


@card(528)
class RopeDog(Monster):
    last_refresh_turn: StateVar[int | None] = StateVar(default=None)

    synergy = SELF.buff(attack=+2) >> SELF.add_keyword(HASTE)

    @on_event(AttackResolvedResult)
    def on_attack_resolved(self, res: AttackResolvedResult, game, **kwargs):
        if res.attacker_id != self.id:
            return None

        if res.attacker_dead:
            return None

        defender = game.entity(res.defender_id)
        if not isinstance(defender, Monster):
            return None

        return OncePerTurn(
            RopeDog.last_refresh_turn,
            SELF.refresh_attacks()
            >> SELF.add_keyword(HASTE),
        )
