from deltacards.dsl.api import *


PLUG = HAS_TRIBE(Tribe.PLUG)


@card(679)
class SmallPlug(Monster):
    targets = HAND & PLUG

    magic = Switch(
        left=TARGET.add_keyword(HASTE),
        right=TARGET.add_keyword(TAUNT)
    )


@card(680)
class Pluggirl(Monster):
    turn_end = Check(
        (SELF.buffs.attack > 0)
        | (SELF.buffs.max_hp > 0)
    ).to(
        SELF.add_keyword(TAUNT)
    )


@card(681)
class Plugboy(Monster):
    _effect = ((HAND & PLUG) >> RANDOM(2)).buff(attack=+1, hp=+1)

    magic = _effect
    dust = _effect


@card(682)
class Revoltplug(Monster):
    magic = For(
        SELF.attack,
        effect=(ENEMY_MONSTERS >> RANDOM(1)).hit(1)
    )


@card(683)
class Hatplug(Monster):
    draw_result: Var[StepResult] = Var(StepResult)

    @on_event(DodgeConsumedResult)
    def on_dodge_consumed(self, res: DodgeConsumedResult, game, **kwargs):
        if res.monster.id != self.id:
            return None

        return YOU.draw((DECK & PLUG).first()).store_result(self.draw_result).to(
            Buff(target=self.draw_result.card_id, attack=+2, hp=+2)
        )


@card(684)
class Werewire(Monster):
    targets = ALLY_MONSTERS & PLUG

    released_card: Var[Card] = Var(Card)

    magic = SELF.catch(TARGET)

    dust = SELF.release_caught_card(var=released_card).to(
        released_card.buff(
            attack=SELF.buffs.attack,
            hp=SELF.buffs.max_hp
        )
        >> released_card.summon(controller=released_card.controller)
    )


@card(685)
class Businessplug(Monster):
    targets = HAND & PLUG

    copied_card: Var[Card] = Var(Card)

    magic = (
        SetVar(var=copied_card, value=TARGET >> EXACT_COPY())
        >> copied_card.set_base_stats(attack=1, hp=1)
        >> copied_card.summon()
    )


@card(687)
class Werewerewire(Monster):
    X: Var[Card] = Var(Card)
    werewire: Var[Card] = Var(Card)

    magic = ForEach(
        ALLY_MONSTERS & PLUG & ~SELF,
        var=X,
        effect=(
            SetVar(var=werewire, value=GENERATE_CARD("Werewire"))
            >> werewire.buff(
                attack=X.buffs.attack,
                hp=X.buffs.max_hp
            )
            >> X.turn_into(werewire)
            >> werewire.catch(X)
        )
    )


@card(882)
class Ramb(Monster):
    magic = YOU.add_artifact(ARTIFACT_BY_NAME("Odd Controller"))
