# Game rules

**IMPORTANT: These rules are unofficial.**

They are my interpretation of the game's rules, based primarily on observation.

Because there are no official game rules, I attempted to make a consistent ruleset so that this engine's behavior is stable and predictable.

Some behavior *may* differ from the official game, especially where its behavior was unclear, inconsistent, or difficult to observe.

If you see that something here is wrong, you can help by pointing it out and proposing the changes.

---

## Overview
A two-player digital card game in which each player brings a 25-card deck and competes in a 1-vs-1 match.

Cards are either Monsters, which occupy the board and can attack, or Spells, which perform one-shot effects.

Your goal is to reduce the opponent's HP to 0.

---

## Building a deck
Each player chooses:
- exactly 25 non-TOKEN cards;
- one Soul;
- two Common Artifacts or one Legendary Artifact.

Cards are either:
- **Monsters**, which occupy board slots and can attack; or
- **Spells**, which perform one-shot effects.

---

## Setup and mulligan
The starting player is chosen randomly.

At the start of the game, each player has 30 HP, and each player's deck is shuffled.

### Mulligan
Each player is shown the first three cards of their deck.

This is the "mulligan": each player (at the same time) chooses any number of these cards to send them to their deck.

Then, decks are shuffled, and each player draws cards equal to the cards sent.

---

## Players
Each player has:
- current and maximum HP;
- gold;
- a deck, hand, board, Dustpile, and Erased zone;
- a Soul;
- equipped Artifacts;
- a personal turn count;
- a fatigue count.

---

## Souls and Artifacts
Each Soul and Artifact has its own effects that can affect the game.

### Souls
Before the game starts, each player chooses one of the seven Souls.

The available Souls are Kindness, Determination, Patience, Bravery, Integrity, Perseverance, and Justice.

### Artifacts
Before the game starts, each player chooses either two non-Legendary Artifacts or one Legendary Artifact.

Each player's selected Artifacts start the game enabled.

They can be disabled by effects that specifically instruct the player to disable one or more Artifacts.

Players can obtain additional Artifacts during the game through card effects.

There is no general limit to how many Artifacts a player can have.

### Quests
A Quest is an Artifact with a progress goal and a reward.

Quest Artifacts follow the ordinary Artifact rules.

A Quest Card starts its associated Quest at Game Start when that card is in
its controller's hand or deck after mulligans have finished. Starting a Quest
equips its Quest Artifact.

A Quest's progress is shown by its counter. A Quest completes when its progress
reaches its goal.

- A repeatable Quest resolves its reward, then resets its progress to 0.
- A non-repeatable Quest resolves its reward, then becomes disabled.
- Progress cannot exceed the Quest goal.
- Completing a Quest does not carry excess progress into the next completion.

---

## Board Slots and Enchantments
Each player has four persistent Board Slots, numbered from left to right.

A Board Slot may contain:
- one Monster;
- one Enchantment.

The Monster and Enchantment in a slot are independent.
An Enchantment remains attached to its slot when the Monster in that slot moves or dies.

An effect can target an empty or occupied Board Slot.

If an effect Enchants a slot that already has an Enchantment, the old Enchantment is removed and replaced by the new one.

Enchantments may have their own abilities, continuous effects, and counters.

---

## Card zones
Deck: A face-down stack. Its current contents and order are hidden from both players.

Hand: Contains up to 7 cards. Its contents are visible only to its owner.

Board: Contains 8 total slots, with 4 slots belonging to each player. Each slot can hold at most one Monster.

Dustpile: A face-up pile for killed Monsters. This is a public zone.

Erased: A zone for cards removed from the game. This is a public zone.

Stack: A zone for Spells that are currently resolving. This is a public zone.

---

## Turn flow
During your turn, while no effect or choice is waiting to resolve, you may normally:
- play a Monster or a Spell;
- declare an attack;
- end your turn.

There are no phases.
During your turn, you may play Monsters, play Spells, and attack in any order you choose.

Gold persists between turns.

A player's personal turn count begins at 0 and increases at the start of each of that player's turns.
A player can end their turn by clicking the End Turn button.

### Start of turn
At the start of your turn:
1. Your personal turn count increases by 1.
2. You gain X gold, where X is the current player's turn number (max. 10).
   - If you are not the starting player, this is turn 10 or earlier and your personal turn count is odd, you gain additional 1 gold.
3. For each Monster you control: decrement its Paralyzed counter and remove Transparency. It becomes able to attack again.
4. You draw one card.
5. Your Turn Start effects resolve.

### End of turn
At the end of your turn:
1. Each Monster you control loses Charge and Haste, and heals 3 HP if it has Candy.
2. Delay effects resolve.
3. Your Turn End effects resolve.

### Turn skipping
An effect can cause a player to skip their next turn.

A skipped turn only skips the opportunity to perform normal player actions.

It still receives normal start-of-turn and end-of-turn processing.

---

## Gold costs and playing cards
Each card has a current gold cost.
Effects may increase or decrease that cost.

To play a card from your hand, you must have enough gold to pay its current cost.

Monsters: Play the Monster into an empty board slot on your side.
If the Monster has a Magic effect that requires a target, you will be prompted to choose one.

Spells: Play the Spell from your hand.
If the Spell requires a target, you will be prompted to choose one.
The Spell resolves and is then removed from the Stack.

---

## Drawing cards & Fatigue
Cards are always drawn one at a time.

If a player attempts to draw while their deck is empty, their fatigue counter, starting at 0, increases by 1.
They then take damage equal to their new fatigue counter.

If a player would draw a card while at 7 cards, that card is revealed to both players and Erased instead of going to hand.

If a monster would be sent from a board to a player's hand while that player is at 7 cards, it is killed instead.

If a card would be added to player's hand by any other way while at 7 cards, the action that attempted to move a card "fizzles".

All cards added from the deck to the hand are considered "drawn" for the purpose of trigger handling.

Intended exception: cards drawn at the start of the game, including via "mulligan", are not treated as "drawn".

### Overdraw
If a player would draw while their hand already contains 7 cards, the card is Erased instead.

An overdrawn card still triggers Turbo.

### Moving cards into a full hand
Other effects that try to move cards into a full hand follow these rules:
- A Monster moved from the board to a full hand is killed instead.
- A card moved from the deck to a full hand is overdrawn.
- A card moved from another location to a full hand normally stays where it is because the move fails.

Moving a card from its owner's deck to its owner's hand always counts as drawing it.

### Moving card restrictions
Cards in the Dustpile can't be moved anywhere except the Erased zone.

If an effect instructs you to move a Monster from the Dustpile to any zone other than Erased, this means:
create a copy of that Monster, erase the original, and then perform the intended action on the new copy.

Cards in the Erased zone can't be moved anywhere else.

---

## Card stats
Every card has a name, rarity, cost, and other properties.
Rarities are ordered as follows: `BASE < COMMON < RARE < EPIC < LEGENDARY < DETERMINATION < TOKEN`.

---

## Monster stats and statuses
Every Monster has a cost, Attack, current HP, and maximum HP.
A Monster normally begins with current HP equal to its maximum HP.

Damage lowers current HP without lowering maximum HP.
A permanent positive HP change normally increases maximum HP and current HP by the same amount.

Keywords and statuses modify a card's behavior. Examples: Charge, Haste, Taunt.
A card can have any number of keywords and statuses.

Newly summoned Monsters can't normally attack until their controller's next turn unless they have Charge or Haste.

---

## Playing Monsters
To play a Monster:
- it must be in your hand;
- you must be able to pay its current cost;
- you must have an empty board slot.

A played Monster:
1. has its gold cost paid;
2. may create a Loop copy;
3. is summoned to the board;
4. resolves its Magic effect, if available;
5. resolves its Synergy effect, if its Synergy condition was met;
6. counts as played and summoned, causing applicable reactions to resolve.

Reactions to a Monster being played or summoned happen after its Magic and
Synergy effects resolve. The Monster is already on the board while they resolve.

If a Monster has a targeted Magic effect but there are no legal targets, the Monster may still be played.
Its targeted Magic and its Synergy effects are skipped.

---

## Playing Spells
To play a Spell:
- it must be in your hand;
- you must be able to pay its current cost;
- if it requires a target, at least one legal target must exist.

A played Spell:
1. has its gold cost paid;
2. may create a Loop copy;
3. moves to the Stack;
4. resolves its Magic effect;
5. leaves the Stack;
6. counts as played and cast, causing applicable reactions to resolve;
7. causes eligible Shock effects to trigger if its base cost is at least 2.

Reactions to a Spell being played or cast happen after its Magic resolves and after it leaves the Stack.

If an effect casts a Spell rather than a player manually playing it:
- it does not count as a manually played Spell;
- it does not count for effects that refer to spells being cast (for example, "for each spell you cast this game, do X");
- if the Spell needs a target and the effect did not provide one, a random legal target is chosen;
- choices created during that automatic cast are made randomly;
- if no legal target exists, the Spell's Magic is skipped.

---

## Targets and choices
Some cards require a target when played.

Legal targets are determined using the current game state.

### Manual target selection
If a card has legal targets and no target was supplied, its controller is asked to choose one.

If a Monster has a targeted Magic effect but there are no legal targets:
- the Monster may still be played;
- its targeted Magic and its Synergy effects are skipped.

If a Spell requires a target but has no legal targets:
- the Spell cannot be played.

### Target restrictions
- Transparent Monsters can't be manually selected as attack targets.
- Transparent Monsters can't be selected as on-play targets.
- Darkspawn Monsters can't be selected as on-play Spell targets.
- Other choices made by card effects use the options described by that effect.

Targets are checked again when actions resolve.

If a target is no longer valid, that part of the effect may fail.

---

## Combat
A Monster may normally attack once per turn.
It can't normally attack during the turn it was summoned unless it has Charge or Haste.

The target may be an opponent or one of their monsters.

Transparent Taunt Monsters don't restrict attack targets.
If every defending Taunt Monster is Transparent, Taunt imposes no targeting restriction.

---

## Attack sequence and combat damage
Each attack consists of 3 steps:
1. Attack declaration, made either by a player or by an effect.
2. Combat damage is dealt.
3. Attack resolution step - Charge and Haste are removed; effects such as "After X attacks, do Y" resolve.

### Combat Damage Step
The following is performed in order:
- Attack values of both attacker and defender are calculated;
- the attacker deals damage equal to its Attack to the defender;
- if the defender is a Monster, it deals damage equal to its Attack to the attacker.

---

## Damage
Damage to a Monster is processed in this order:
1. The target must still be a valid Monster on the board.
2. Invulnerable may prevent the damage.
3. Darkspawn may prevent Spell damage.
4. Other damage-changing rules apply.
5. Armor reduces the damage by 1.
6. If the damage is now 0 or less, no damage is dealt.
7. Dodge may consume one counter and prevent the damage.
8. The remaining damage lowers the Monster's HP.
9. Death prevention and killing are checked if the Monster reaches 0 or less HP.
10. Bullseye may trigger if the source brought the Monster to exactly 0 HP and death was not prevented.

Damage beyond the Monster's remaining HP is excess damage.

---

## Monster deaths
When a Monster is killed:
1. Death prevention is checked.
2. KR and Wanted triggers are prepared, if applicable.
3. Its Dust effect is prepared, if it has one and is not Silenced.
4. The Monster is removed from its board slot.
5. Its death is recorded.
6. Its Dust effect resolves, if any.
7. Its death is finalized, and it enters the Dustpile unless its Bullseye or its Dust effect moved it somewhere else.

A Monster resolving a Bullseye or a Dust effect temporarily remains available as the source of that effect.

Its runtime state has not reset at that point.

If the Bullseye or the Dust effect moves it somewhere else, it is not forced into the Dustpile afterward.

A Monster without a Bullseye or a Dust effect normally enters the Dustpile immediately.

An Enchantment on the Monster's former Board Slot remains on that slot.

The engine records the immediate cause of each Monster death:

- **Combat**: lethal combat damage;
- **Damage effect**: lethal non-combat damage;
- **Destroy effect**: an effect that directly kills or destroys the Monster;
- **Other**: a stat change or another rule transition that causes death.

An effect that happens during an attack is not automatically a Combat kill.
Only death caused by combat damage has the Combat cause. For example, a
Support effect that directly destroys a Monster has the Destroy-effect cause.

---

## Monster keywords and statuses

### Keywords
- **Charge**: This monster can attack during its first turn. Overrides Haste. This attribute is removed after attacking or when your turn ends;
- **Haste**: This monster can attack during its first turn, but can't attack the opponent directly. This attribute is removed after attacking or whenever your turn ends;
- **Taunt**: Enemy monsters must kill monsters with this effect before they can attack the player or other ally monsters;
- **KR**: When this monster dies, give its killer +1/+1. If there's no killer (e.g. it was destroyed by the opponent's spell or effect) or if the killer is no longer alive by the time this trigger resolves, give a random other enemy monster +1/+1 instead. If two monsters with KR attack each other and both die as a result of a battle, they are killed even though KR may result in them having positive HP;
- **Candy**: Heal 3 HP to this monster at the end of its controller's turn;
- **Armor**: This monster takes 1 less damage.
- **Transparency**: This monster can't be targeted (when a player chooses targets for a choice-targeting spell or when choosing an attack target). Transparency is removed at the start of this monster's controller's turn;
- **Disarmed**: This monster can't attack;
- **Invulnerable**: This monster is immune to all damage;
- **Silenced**: This monster is silenced;
- **Wanted**: When this monster dies, give 1 gold to its opponent.
- **Darkspawn**: This monster takes no damage from spells, and cannot be targeted by choice-targeting spells.
- **Flowery Power**: This card's Need condition is always fulfilled.
- **Determination**: This monster is immune to Silence. This status is innate to all DETERMINATION rarity monsters;

### Statuses
- **Paralyzed**: This monster cannot attack while the status remains. When Paralyzed is applied, a counter of 2 is set. At the start of the monster's controller's turn, decrease that counter by 1. When the counter reaches 0, remove Paralyzed and the monster can attack again. If an effect attempts to apply Paralyzed to a monster that is already Paralyzed, counter value is not modified;
- **Dodge (X)**: This monster will negate any instance of damage to itself (x) times.
- **Loop (X)**: When you play this card while it has 1 or more Loop, add a copy of this to your hand with -1 Loop.

---

## Silence
Silence follows these rules:
1. A Determination-rarity Monster cannot be Silenced.
2. Its buffs and debuffs are removed.
3. Its keywords are replaced by Silenced.
4. All statuses except Loop are removed.
5. Its active toggleable abilities, such as Shock and Support, are disabled.
6. Its maximum HP is recalculated from its base stats.
7. Its current HP becomes the smaller of:
   - its old current HP; or
   - its new maximum HP.
8. If that would leave it at 0 or less HP, it is left at 1 HP instead.

Silence doesn't permanently prevent the Monster from receiving future changes.

New buffs, debuffs, keywords and statuses may be added after it is Silenced.

---

## Negative effects

For effects that check for or remove "negative effects", the removable
negative effects are:

- a positive cost buff;
- a negative Attack buff;
- a negative maximum-HP buff;
- KR, Disarmed, Silenced, or Wanted;
- Paralyzed.

Damage and missing HP are not negative effects for this purpose. Continuous
modifiers are also not removed. Removing Silenced does not restore buffs,
keywords, statuses, or abilities that were already removed by Silence.

---

## Monster tribes
Some Monsters have a special property named "Tribe".
Examples include Dog, Amalgamate, Frog, and Plant.

Similarly themed cards often share the same Tribe and have effects that reward playing other cards from that Tribe.

There is also a special Tribe named "All monster tribes".
Monsters with that Tribe are considered to have every concrete Tribe for the purpose of card effects.

Each player tracks the Monster tribes they have played during the current turn.
When a Monster is played, its Synergy condition is checked before its own Tribes are added to that record.
Synergy succeeds if a previously played allied Monster had an overlapping Tribe.

---

## Named card effects (abilities) and triggers
- **Magic**: The card will trigger its effect when played (only via playing it from hand).
- **Synergy**: The monster will trigger its effect when played and if an ally monster of the same tribe has been played this turn.
- **Dust**: The monster will trigger its effect when dying.
- **Delay**: The card will trigger this effect at the end of the turn it was played. Delay is scheduled as an independent effect. It will trigger even if the card is killed, silenced or removed from the board before the turn ends.
- **Game Start**: This effect will be triggered after setup and mulligans, before the first turn begins. A card may also trigger Game Start while it is in its controller's hand or deck.
- **Turn Start**: The entity will trigger its effect at the start of its turn.
- **Turn End**: The entity will trigger its effect at the end of its turn.
- **Shock**: After you cast a spell with a base cost of 2 or more, trigger this effect.
- **Support**: This monster will trigger its effect each time right before another ally monster attacks, before combat damage.
- **Turbo**: This card will trigger its effect when drawn.
- **Bullseye**: If this entity brings a monster to exactly 0 HP, trigger this effect.

---

## Ability keywords
- **Need**: This card's Magic effect can only trigger from its normal play if
  the following condition is met. The condition is evaluated after play and
  target validation, immediately before the card leaves the hand. That result
  is retained for the rest of that play. Triggering Magic directly through
  another effect does not reevaluate Need.
- **Program (X)**: If you have at least X gold, spend that gold to trigger the following effect.
- **Switch**: Whenever this effect triggers, if the monster is on the left side of the board do the first part of the effect, otherwise do the second one.

---

## "Catch" mechanic
To "Catch X" in a Monster effect means to remove X from its original location and store its card data in that Monster.

A Monster can store at most one caught card.
Only the caught card's template and original controller are remembered.
All other runtime data is lost.

Releasing a caught card creates a new runtime Card from the stored information.
The releasing effect must separately specify where that Card is placed.

If effect text says "release a card" but doesn't specify where, the zone to release to is the board.

If effect text says "release a card" but doesn't specify controller of the newly released card, the new controller is the original controller of that card.

---

## Ordering of reactions and multi-target effects
When several entities react to the same event, sources are ordered as follows:
1. the current turn player's non-Silenced Monsters, from left to right;
2. the current turn player's Enchantments, from left to right;
3. the current turn player's Soul;
4. the current turn player's enabled Artifacts, in equip order;
5. the other player's non-Silenced Monsters, from left to right;
6. the other player's Enchantments, from left to right;
7. the other player's Soul;
8. the other player's enabled Artifacts, in equip order.

Reactions to an event resolve before follow-up effects produced by the same action.

## Some other phrases commonly used in effect texts that aren't keywords
- "draw up to X cards" means "repeat X times: if your deck isn't empty and your hand isn't full, draw a card";
- "everywhere" means "on your board, in your hand, and/or in your deck".
