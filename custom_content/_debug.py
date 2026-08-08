"""
This file contains optional cards for debugging.
Its name begins with an underscore (`_`), so it is not loaded by default.

If you want to use these cards in a game, make a copy of this file and name the copy `debug.py`.
Place it in the same folder as this file or in a subfolder.
You can then tweak the copy however you like.

Simply renaming this file is not recommended, as doing so may cause conflicts when updating.
"""

from deltacards.dsl.api import *


BASE_ID = 1_500_000

DEBUG_FIRST_CARD_ID = BASE_ID + 1
DEBUG_LAST_CARD_ID = BASE_ID + 7

DEBUG_CARD_TEMPLATES = (
    CARD_LIBRARY
    & (TEMPLATE_ID >= DEBUG_FIRST_CARD_ID)
    & (TEMPLATE_ID <= DEBUG_LAST_CARD_ID)
)

CUSTOM_NON_DEBUG_CARD_TEMPLATES = (
    CARD_LIBRARY
    & IS_CUSTOM_CONTENT
    & ~(
        (TEMPLATE_ID >= DEBUG_FIRST_CARD_ID)
        & (TEMPLATE_ID <= DEBUG_LAST_CARD_ID)
    )
)


@card(
    BASE_ID + 1,
    name="Debug Menu",
    description="Look at all Debug cards. Choose one to add to your hand.",
    rarity=CardRarity.TOKEN,
    cost=0,
    image=ExistingImage("Arcane_Codes"),
)
class DebugMenu(Spell):
    magic = YOU.choose(
        DEBUG_CARD_TEMPLATES >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(
    BASE_ID + 2,
    name="Pick a Blueprint",
    description="Look at all custom cards. Choose one to add to your hand.",
    rarity=CardRarity.TOKEN,
    cost=0,
    image=ExistingImage("Create_a_Machine"),
)
class PickABlueprint(Spell):
    magic = YOU.choose(
        CUSTOM_NON_DEBUG_CARD_TEMPLATES >> GENERATE_CARD()
    ).to(
        CHOICE_SELECTED.to_hand()
    )


@card(
    BASE_ID + 3,
    name="Endless Reinforcements",
    description=(
        "{{KW:LOOP}} (99). Choose a {{COST}}, earn that much {{GOLD}}, "
        "then choose a card of that {{COST}}. Add it to your hand."
    ),
    rarity=CardRarity.TOKEN,
    cost=0,
    statuses={
        LOOP: 99,
    },
    image=ExistingImage("Mercenary_Hire"),
)
class EndlessReinforcements(Spell):
    chosen_cost: Var[int] = Var(int)

    magic = YOU.choose(
        (
            CARD_LIBRARY
            >> LIMIT_PER(COST, 1)
        ) >> GENERATE_CARD()
    ).to(
        SetVar(
            var=chosen_cost,
            value=CHOICE_SELECTED.base.cost
        )
        >> YOU.earn_gold(chosen_cost)
        >> YOU.choose(
            (CARD_LIBRARY & (COST == chosen_cost))
            >> GENERATE_CARD()
        ).to(
            CHOICE_SELECTED.to_hand()
        )
    )


@card(
    BASE_ID + 4,
    name="TRANSMIT KROMER",
    description="Earn 100 {{GOLD}}.",
    rarity=CardRarity.TOKEN,
    cost=0,
    image=ExistingImage("Generosity"),
)
class TransmitKromer(Spell):
    magic = YOU.earn_gold(100)


@card(
    BASE_ID + 5,
    name="Reset",
    description=(
        "{{KW:ERASE}} the board, hands and decks. "
        "Add {{CARD:1500001|1}} with {{KW:LOOP}} (99) to your hand."
    ),
    rarity=CardRarity.TOKEN,
    cost=0,
    image=ExistingImage("Royal_Determination"),
)
class Reset(Spell):
    generated_card: Var[Card] = Var(Card)

    magic = (
        (
            BOARD | OPPONENT_BOARD
            | HAND | OPPONENT_HAND
            | DECK | OPPONENT_DECK
        ).erase()
        >> SetVar(
            var=generated_card,
            value=GENERATE_CARD("Debug Menu")
        )
        >> generated_card.set_status(LOOP, value=99)
        >> generated_card.to_hand()
    )


@card(
    BASE_ID + 6,
    name="That Dog's a Bomb!",
    description=(
        "Choose a card in your hand to send to the enemy hand. "
        "The opponent earns {{GOLD}} equal to its {{COST}} and plays it if possible."
    ),
    rarity=CardRarity.TOKEN,
    cost=0,
    image=ExistingImage("Control_Wire"),
)
class ThatDogsABomb(Spell):
    targets = HAND

    magic = TARGET.to_hand(controller=OPPONENT).to(
        OPPONENT.earn_gold(TARGET.cost)
        >> Play(player=OPPONENT, card=TARGET)
    )


@card(
    BASE_ID + 7,
    name="Cloning (beta ver.)",
    description=(
        "Choose a card in your hand or on the board. "
        "Add an exact copy of it to your hand."
    ),
    rarity=CardRarity.TOKEN,
    cost=0,
    image=ExistingImage("Cloning"),
)
class CloningBetaVer(Spell):
    targets = HAND | BOARD

    magic = (TARGET >> EXACT_COPY()).to_hand()
