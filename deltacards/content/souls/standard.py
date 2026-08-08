from deltacards.dsl.api import *
from deltacards.model.souls import Soul, soul


@soul('EMPTY')
class EmptySoul(Soul):
    """Soul with no effects to simplify testing"""
    pass


@soul('KINDNESS')
class Kindness(Soul):
    turn_end = Check(YOU.turn >= 3).to(
        YOU.heal(1)
        >> Check(ALLY_MONSTERS & DAMAGED).to(
            (ALLY_MONSTERS & DAMAGED).heal(1),
            else_=(ALLY_MONSTERS >> RIGHTMOST).buff(hp=+1)
        )
    )


@soul('DETERMINATION')
class Determination(Soul):
    def __init__(self, id: int, controller_id: PlayerId):
        super().__init__(id, controller_id)

        self.extra_life = True

    def game_start(self, ctx: 'ActionContext'):
        controller = self._get_controller(ctx)
        controller.next_lost_soul = 0
        return YOU.add_artifact(ARTIFACT_BY_NAME("Save"))

    def on_would_die(self, entity: Entity, **kwargs):
        if entity.id == self.controller_id and self.extra_life:
            self.extra_life = False
            return entity.actions.set_hp(5)

        return None


@soul('PATIENCE')
class Patience(Soul):
    turn_end = Check(
        (YOU.turn % 2 == 0)
        & (COUNT(HAND) < MAX_HAND_SIZE)
        & (COUNT((HAND | DECK) & (TEMPLATE_NAME == "Change of Winds")) == 0)
    ).to(
        GENERATE_CARD("Change of Winds").to_deck(pos='top')
    )


@soul('BRAVERY')
class Bravery(Soul):
    turn_start = Check(YOU.turn % 3 == 0).to(
        Check(COUNT(HAND) < MAX_HAND_SIZE).to(
            GENERATE_CARD("Recruitment").to_hand(),
            else_=GENERATE_CARD("Draft").to_deck()
        )
    )


@soul('INTEGRITY')
class Integrity(Soul):
    turn_start = Check(YOU.turn > 10).to(
        YOU.earn_gold(1)
    )
    turn_end = Check(YOU.turn > 1).to(
        Check(SPENT_GOLD_THIS_TURN > SPENT_GOLD_LAST_TURN).to(
            YOU.earn_gold(1)
        )
    )


@soul('PERSEVERANCE')
class Perseverance(Soul):
    turn_start = ((ENEMY_MONSTERS & ~HAS_KEYWORD(KR)) >> MAX(ATTACK)).add_keyword(KR)


@soul('JUSTICE')
class Justice(Soul):
    turn_start = (ENEMY_MONSTERS >> MIN(HP)).hit(1)
