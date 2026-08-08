# Creating Custom Content

This guide walks you through creating two custom cards:

1. **Final Knight**, a straightforward Monster with Magic and Bullseye.
2. **Ad Sign**, a more advanced Monster that reacts when another Monster is summoned.

Along the way, you will learn how card metadata, abilities, selectors, and event handlers fit together.

> **Safety warning:** Custom content is executable Python code. Only install custom-content files from people and sources you trust.

---

## Before you begin

Custom content belongs in the following directory:

```text
custom_content/
```

The directory is relative to where the simulator is started.

Create a new file inside it named:

```text
custom_content/tutorial_cards.py
```

Add this import at the top:

```python
from deltacards.dsl.api import *
```

This gives the file access to the public card-definition API.

Custom-content files are loaded when the simulator starts.
After changing a file, restart the simulator.

### Choosing card IDs

Every custom card needs a unique numeric ID. This guide uses:

```python
1_000_001
1_000_002
```

Use large positive IDs for your own cards, and do not reuse an ID already used by another card.

---

# Part 1: Final Knight

Our first card is:

> **Final Knight**  
> **Stats**: 9G / 6 ATK / 9 HP  
> <u>Magic</u>: Deal 3 DMG to monsters adjacent to this.  
> <u>Bullseye</u>: Gain <u>Dodge</u> (1).

Add the following below the import in `tutorial_cards.py`:

```python
@card(
    1_000_001,
    name="Final Knight",
    description=(
        "{{KW:MAGIC}}: Deal {{DMG:3}} to monsters adjacent to this. "
        "{{KW:BULLSEYE}}: Gain {{KW:DODGE}} (1)."
    ),
    rarity=EPIC,
    cost=9,
    attack=6,
    hp=9,
    image=ExistingImage("Knight_Knight"),
)
class FinalKnight(Monster):
    magic = ADJACENT(SELF).hit(3)

    bullseye = SELF.set_status(
        DODGE,
        value=SELF.status(DODGE) + 1
    )
```

Then, save the file.


## Add Final Knight to a deck and test it

Replace one or more existing card IDs with `1000001` in the deck code's `cardIds` list.

Pass that JSON or base64 deck code to the `--p1-deck` (for console) or `--human-deck` (for web UI).

Then, restart the simulator.

### Testing through the web UI

Make sure the [deltacards Bridge](https://raw.githubusercontent.com/rashidsh/deltacards/main/deltacards/app/websocket/userscripts/deltacards-bridge.user.js) UnderScript plugin is installed and enabled, and that **Load custom content** is enabled.

If you want to see custom cards and artifacts in the deck editor, also enable **Load custom content everywhere except in online games**.

Then, start a local game through the plugin's settings.

## Understanding the definition

### The `@card(...)` section

```python
@card(
    1_000_001,
    name="Final Knight",
    ...
)
```

This is a **decorator**. You can think of it as the card's registration form.

It supplies the card's basic information:

- `1_000_001` is its unique card ID;
- `name` is its displayed name;
- `description` is its displayed effect text;
- `rarity` controls its rarity;
- `cost` is its Gold cost;
- `attack` and `hp` are its starting Monster stats;
- `image` specifies a image to use.

`ExistingImage("Knight_Knight")` reuses an image of the monster "Knight Knight" for simplicity.

> For additional optional card metadata, such as starting keywords, statuses, and localizations, see [Card definition reference](#card-definition-reference).

### Description markup

Text such as:

```text
{{KW:MAGIC}}
{{KW:BULLSEYE}}
{{KW:DODGE}}
{{ATK}}
{{HP}}
```

is display markup used by the frontend for keyword / stat formatting and icons.

The description does not create the card's behavior.
It only tells the player what the card is intended to do.
The Python ability definitions implement the actual effect.

### The class

```python
class FinalKnight(Monster):
```

This creates a new Monster definition named `FinalKnight`.

Everything indented inside the class defines that Monster's behavior.

### Magic

```python
magic = ADJACENT(SELF).hit(3)
```

This can be read from left to right:

- `SELF` means the Final Knight whose ability is resolving;
- `ADJACENT(SELF)` selects Monsters immediately to its left and right;
- `.hit(3)` deals 3 damage to each selected Monster.

For example, if Final Knight is in slot 2, the effect can hit Monsters in slots 1 and 3.

### Bullseye

```python
bullseye = SELF.set_status(
    DODGE,
    value=SELF.status(DODGE) + 1
)
```

Bullseye triggers when Final Knight brings a Monster to exactly 0 HP.

This effect:

1. reads Final Knight's current Dodge counter;
2. adds one;
3. stores the new value.

Adding to the current value is important. If Final Knight already has Dodge (1), another Bullseye gives it Dodge (2) instead of resetting it to 1.

## Expected gameplay result

When Final Knight is played:

- it enters the board;
- its Magic deals 3 damage to adjacent Monsters;
- if that damage brings a Monster to exactly 0 HP, Final Knight gains one Dodge;
- Final Knight can also trigger Bullseye through other damage it deals, such as combat damage.

Try placing a Monster with exactly 3 HP next to the slot where you play Final Knight. Final Knight should destroy it and gain Dodge (1).

---

# Part 2: Learning from an existing card

One of the best ways to make custom content is to find an existing card with a similar effect and study its implementation.

For our second card, we will learn from **Spider Sign**, whose implementation is located at:

```text
deltacards/content/cards/tribes/arachnids.py
```

Open that file and search for:

```python
class SpiderSign
```

You should find an event handler shaped like this:

```python
    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id != self.controller_id:
            return None

        if not res.monster.has_tribe(Tribe.ARACHNID):
            return None

        return SELF.buff(attack=+1)
```

It basically does the following:

1. listen for a Monster being summoned;
2. check whether the summoned Monster is relevant;
3. return `None` when nothing should happen;
4. return an effect when all conditions match.

---

# Part 3: Ad Sign

We will adapt Spider Sign's event-handler pattern to create:

> **Ad Sign**  
> **Stats**: 5G / 5 ATK / 6 HP  
> After an enemy monster with <u>Haste</u> is summoned, it attacks this monster.  
> <u>Magic</u>: Give all monsters in the enemy hand <u>Haste</u>.

Add this second definition below `FinalKnight`:

```python
@card(
    1_000_002,
    name="Ad Sign",
    description=(
        "After an enemy monster with {{KW:HASTE}} is summoned, it attacks this monster. "
        "{{KW:MAGIC}}: Give all monsters in the enemy hand {{KW:HASTE}}."
    ),
    rarity=RARE,
    cost=5,
    attack=5,
    hp=6,
    image=ExistingImage("Spamton_Poster"),
)
class AdSign(Monster):
    magic = (OPPONENT_HAND & IS_MONSTER).add_keyword(HASTE)

    @on_event(MonsterSummonedResult)
    def on_monster_summoned(self, res: MonsterSummonedResult, game, **kwargs):
        if res.monster.controller_id == self.controller_id:
            return None

        if not res.monster.has_keyword(HASTE):
            return None

        return RESOLVE_ENTITY(res.monster_id).force_attack(SELF)
```

Save the file and restart the simulator again.

## Ad Sign's Magic

```python
magic = (OPPONENT_HAND & IS_MONSTER).add_keyword(HASTE)
```

This expression has two parts.

First, it selects cards:

```python
OPPONENT_HAND & IS_MONSTER
```

- `OPPONENT_HAND` selects cards in the opponent's hand;
- `&` means "filter using the following condition.";
- `IS_MONSTER` keeps only Monsters.

It then gives Haste to these monsters:

```python
.add_keyword(HASTE)
```

## Listening for events

```python
@on_event(MonsterSummonedResult)
```

This tells the game to call the method below after a monster is summoned.

The method name:

```python
on_monster_summoned
```

is chosen for readability. The `@on_event(...)` line is what connects it to the summon event.

## Ignoring allied Monsters

```python
if res.monster.controller_id == self.controller_id:
    return None
```

This compares the summoned Monster's controller with Ad Sign's controller.

If they are the same, the summoned Monster is an ally. Returning `None` means:

> This event does not cause Ad Sign to do anything.

## Checking for Haste

```python
if not res.monster.has_keyword(HASTE):
    return None
```

If the enemy Monster does not have Haste, the handler stops.

At this point, any Monster that reaches the final `return` is:

- an enemy Monster;
- currently marked with Haste.

## Forcing the attack

```python
return RESOLVE_ENTITY(res.monster_id).force_attack(SELF)
```

The summon result contains a snapshot of the summoned Monster:

```python
res.monster
```

A snapshot is a saved, read-only description of the Monster at the time it was summoned.
It is useful for reading event information, such as checking who controlled the Monster or whether it had Haste:

```python
res.monster.controller_id
res.monster.has_keyword(HASTE)
```

However, a snapshot is not the live Monster in the current game state.

Other reactions may change the Monster before Ad Sign's returned effect resolves.
For example, another Monster might have an ability such as:

> After an enemy monster is summoned, deal 1 DMG to it.

That ability could change the summoned Monster after the snapshot was created.
It could also damage, move, or destroy the Monster.

```python
RESOLVE_ENTITY(res.monster_id)
```

looks up the current live Monster using the runtime ID stored in the result.

Finally:

```python
.force_attack(SELF)
```

makes that live Monster attack Ad Sign.
If the Monster is no longer available when the effect resolves, the forced attack fails normally.

## `self` versus `SELF`

These names look similar but have different purposes.

Lowercase `self`:

```python
self.controller_id
```

is the ordinary Python object available while the event handler is being called.

Uppercase `SELF`:

```python
.force_attack(SELF)
```

is a card-definition selector. It means "the entity whose returned effect is resolving."

A useful rule is:

- use lowercase `self` when checking ordinary values inside a Python method;
- use uppercase `SELF` when building an effect that will resolve afterward.

## Expected gameplay result

When Ad Sign is played:

1. every Monster currently in the enemy hand gains Haste;
2. Ad Sign remains on the board and listens for summon events;
3. when an enemy Monster with Haste is summoned, that Monster is forced to attack Ad Sign.

The reaction also works with an enemy Monster that received Haste from another source.

---

# Reusing patterns from existing cards

When designing a card:

1. Split its text into trigger, conditions, and effect.
2. Find one or more existing cards, artifacts or other types of content with a similar pattern.
3. Copy only the relevant implementation.
4. Adapt its conditions and effect for your card.

Existing cards use the short `@card(existing_id)` form because their metadata already comes from the original card library.
A new custom card should use the complete decorator form shown in this guide.

---

# Optional: Use custom artwork

Both tutorial cards begin with existing artwork.

For Ad Sign, you can use the following example image:

![Ad Sign](assets/ad_sign.png)

Download the image and save it as:

```text
custom_content/images/ad_sign.png
```

Then replace:

```python
image=ExistingImage("Spamton_Poster"),
```

with:

```python
image=CustomImage("images/ad_sign.png"),
```

Custom image paths are relative to the Python file containing the definition.

Card images should be `160 x 90` pixels in size.

Restart the simulator after changing or replacing an image.

# Card definition reference

The `@card(...)` decorator supports many additional optional fields that you can specify when defining a card:

```python
@card(
    1_000_001,
    name="Final Knight",
    description=(
        "{{KW:MAGIC}}: Deal {{DMG:3}} to monsters adjacent to this. "
        "{{KW:BULLSEYE}}: Gain {{KW:DODGE}} (1)."
    ),
    rarity=EPIC,
    cost=9,
    attack=6,
    hp=9,
    keywords=HASTE | TAUNT | ARMOR,
    statuses={
        DODGE: 1,
        LOOP: 3,
    },
    expansion=Expansion.DELTARUNE,
    tribes=[Tribe.ROYAL_GUARD],
    # soul_id='KINDNESS',  # for spells only
    image=ExistingImage("Knight_Knight"),
    localizations={
        'ru': LocalizedText(
            name="Final Knight",
            description=(
                "{{KW:MAGIC}}: Наносит {{DMG:3}} монстрам на соседних слотах этой карты. "
                "{{KW:BULLSEYE}}: Получает +1 {{KW:DODGE}}."
            ),
        ),
    },
)
class FinalKnight(Monster):
    ...
```

# Other content types

Cards are not the only content that can be defined in Python.
The same general pattern is used for Artifacts, Quests, Souls, and Enchantments.

## Artifact

```python
@artifact(
    1_001_001,
    name="Custom Artifact",
    description="{{KW:TURN_START}}: Heal 1 {{HP}} to you.",
    rarity=ArtifactRarity.COMMON,
    image=ExistingImage("Reverberation"),
)
class CustomArtifact(Artifact):
    turn_start = YOU.heal(1)
```

## Quest Artifact

Quests are implemented almost just like artifacts, except they are rendered differently.

```python
@artifact(
    1_001_002,
    name="Custom Quest",
    description="{{KW:QUEST_GOAL}}: 5. {{KW:QUEST_REWARD}}: Heal 20 {{HP}} to you. {{KW:TURN_START}}: Gain a counter.",
    rarity=ArtifactRarity.TOKEN,
    image=ExistingImage("Power_of_Friendship"),
    overlay=ExistingImage("Power_of_Friendship"),
    quest_goal=5,
)
class CustomQuest(QuestArtifact):
    turn_start = (
        SELF.update_artifact_counter(+1)
        >> Check(SELF.counter >= SELF.quest_goal).to(
            YOU.heal(20)
            >> SELF.toggle_artifact(False)
        )
    )
```

This example quest is non-repeatable. At five progress, it heals its controller and disables itself.

## Soul

```python
@soul(
    'CUSTOM',
    name="Custom Soul",
    description="{{KW:TURN_START}}: Heal 1 {{HP}} to you.",
    image=ExistingImage("KINDNESS"),
)
class CustomSoul(Soul):
    turn_start = YOU.heal(1)
```

## Enchantment

```python
@enchantment(
    'custom-enchantment',
    name="Custom Enchantment",
    description="{{KW:TURN_START}}: Heal 1 {{HP}} to you.",
    image=CustomImage("images/custom_enchantment.png"),
    overlay=CustomImage("images/custom_enchantment_overlay.png"),  # optional field
    log=CustomImage("images/custom_enchantment_log.png"),  # optional field
)
class CustomEnchantment(Enchantment):
    turn_start = YOU.heal(1)
```

A card effect must create it on a Board Slot, for example:

```python
targets = ALLY_SLOTS

magic = TARGET.enchant(
    ENCHANTMENT_BY_NAME('custom-enchantment')
)
```
