# Ink Language — Extended Reference

## Weave in Depth

Weave is ink's key structural innovation: choices and gathers form a forward-flowing chain without needing explicit knot names.

```ink
=== escape ===
I ran through the forest.

    * I checked my pockets. <>
    * I kept on running. <>
    * I cheered. <>

- The road was near!

    * I reached the road[]. And would you believe it?
    * (aside) I should mention Mackie is reliable[]. Normally.

- The road was empty. Mackie was gone.
```

### Nested Weave

```ink
- "Murder or suicide?"
    * "Murder!"
        "Who did it?"
        * * "Japp!"
        * * "Hastings!"
        - - "You must be joking!"
        * * "I am deadly serious."
    * "Suicide!"
        "Are you sure?"
        * * "Quite sure."
- Mrs. Christie lowered her manuscript.
```

Level depth: `*`, `* *`, `* * *`… / `-`, `- -`, `- - -`…

### Labelled Gathers & Options

```ink
- (hub)
    * (greet) [Greet him] 'Hello.'
    * (threaten) 'Get out of my way.'
- 'Hmm,' he replies.
* { greet } 'Nice day?' // only if greeted
* { threaten } [Shove him] -> fight    // only if threatened
```

---

## Advanced Variable Text

### Multiline Alternatives

```ink
{ stopping:
    - I entered the casino.
    - I entered again.
    - Once more, I went in.
}

{ shuffle:
    - Ace of Hearts.
    - King of Spades.
}

{ cycle:
    - I held my breath.
    - I waited impatiently.
}

{ once:
    - Would my luck hold?
    - Could I win?
}
```

### Modified Shuffles

```ink
{ shuffle once:   ... }     // play once, then nothing
{ shuffle stopping: ... }   // shuffle all-but-last, then stick on last
```

---

## Lists — Advanced Operations

### Custom Numerical Values

Values default to 1, 2, 3… in declaration order. Override any of them, and unspecified neighbours continue incrementing by 1:

```ink
LIST primes = two = 2, three = 3, five = 5
LIST integers = zero = 0, one, two, three  // one=1, two=2, three=3
LIST primesGap = two = 2, three, five = 5  // three=3 (auto), five=5
```

Brackets for initial state work around the whole term or just the name: `LIST primes = (two = 2), (three) = 3, (five = 5)`.

### Type Casting Numerics

Integer division truncates, which is often surprising. Use `INT()`, `FLOOR()`, and `FLOAT()` to control conversions:

```ink
{INT(3.2)}    // 3
{FLOOR(4.8)}  // 4
{INT(-4.8)}   // -4 (toward zero)
{FLOOR(-4.8)} // -5 (toward negative infinity)
{FLOAT(2) / 3}  // 0.666667
```

`RANDOM()` returns an integer, so `RANDOM(1, 10000) / 10000` is always 0. Force float division with `FLOAT(RANDOM(1, 10000)) / 10000`.

### Comparing Lists

- `A > B` — every value in A is numerically greater than every value in B
- `A >= B` — A's range entirely overlaps or exceeds B's range
- Standard `==`, `!=`, `<`, `<=` also work for single-value lists

### Intersection

```ink
{ desiredValues ^ actualValues }   // returns overlapping elements
{ LIST_COUNT(a ^ b) > 0: overlap exists }
```

### Inversion

```ink
~ GuardsOnDuty = LIST_INVERT(GuardsOnDuty)  // flip all in/out states
```

### Range Slice

```ink
LIST_RANGE(LIST_ALL(primeNumbers), 10, 20)   // values between 10–20 inclusive
```

### Type-refreshing an Empty List

```ink
LIST ValueList = first, second, third
VAR myList = ()
~ myList = ValueList()     // empty list that knows its type; LIST_ALL works
```

### Multi-family Lists

```ink
LIST Characters = Alfred, Batman, Robin
LIST Props = champagne_glass, newspaper

VAR BallroomContents = (Alfred, Batman, newspaper)

* { BallroomContents ? (Batman, Alfred) } [Talk to both] ...
```

---

## Tunnels — Advanced

### Returning Somewhere Else from a Tunnel

```ink
=== hurt(x) ===
    ~ stamina -= x
    { stamina <= 0:
        ->-> youre_dead    // return, but divert to youre_dead instead of caller
    }
    ->->
```

### Conversation Loop with Tunnel Exit

```ink
-> talk_to_jim ->

=== talk_to_jim ===
- (opts)
    * [Ask about shields] -> shields ->
    * [Stop talking]      ->->
- -> opts

= shields
    { warp_lacels : ->-> argue }    // break out to argue if other topic visited
    "Shields are fine."
    ->->
```

---

## Threads — Advanced

Threads fork content and collect options from multiple sources before presenting them together. Unlike tunnels, they do **not** run a separate flow to completion; they gather options and the chosen branch becomes the main flow.

```ink
== hallway ==
<- characters_present(HALLWAY)
* [Open the drawers] -> examine_drawers
* [Leave] -> corridor
- -> run_location

== characters_present(room)
    { generals_location == room: <- general_dialogue }
    { doctors_location == room:  <- doctor_dialogue  }
    -> DONE
```

Key rules:

- Global variables are **not** forked between threads. Local variables and parameters are.
- Threads end when they run out of content; mark intentional ends with `-> DONE`.
- `-> END` inside a thread ends the **entire story**, not just the thread.
- A stitch reached via thread cannot return with `->->` (no call stack). Every branch must divert explicitly, or be gated by `+ { condition }` to suppress when not wanted.

### Implicit Threads (Pickups)

Adding an *extra* level of `*` to a weave block causes the flow to both enter the block and continue past it — an "implicit thread". Useful for follow-up choices and contextual pickups that drop back into the surrounding flow when not taken.

```ink
=== talk_about_dog ===
* "What a delightful dog you have!"
  "Thank you. Mr Scruffles is a true gentleman. Gentledog."
-
  * * (gentledog) "Gentledog is NOT a word."
      "It is for Scruffles. It is!"
-
  * * { gentledog } "I respectfully disagree."
      My companion tickles the mutt.
- ->->
```

The double-`*` choices are offered only after the parent choice has been taken, and the flow drops through the gather even if none are chosen.

---

## Parameters & Divert Targets as Values

```ink
VAR current_epilogue = -> everybody_dies

=== continue_or_quit ===
* [Give up] -> current_epilogue    // diverts to the stored divert

=== generic_sleep(-> waking) ===
You fall asleep.
-> waking
```

---

## String Queries

```ink
{ "Yes, please." == "Yes, please." }   // true
{ "No, thanks." != "Yes, please." }    // true
{ "Yes, please" ? "ease" }             // substring test; true
```

---

## Database Pattern

Ink has no object/record type, but the standard idiom is a function that switches on a list item and returns the requested field via a helper. This is recommended over CONST-based ad-hoc lookups, and it allows values to vary at runtime:

```ink
LIST People = ElizabethBennett, DavidDarcy, JimBroadbent
LIST Data = Name, Age, Title

=== function PersonData(who, what)
{ who:
- ElizabethBennett: ~ return data(what, "Elizabeth Bennett", 22, "Miss")
- DavidDarcy:       ~ return data(what, "David Darcy", 37, "Mr")
- JimBroadbent:     ~ return data(what, "Jim Broadbent", 79, "Sir")
}

=== function data(what, nameData, ageData, titleData)
{ what:
- Name:  ~ return nameData
- Age:   ~ return ageData
- Title: ~ return titleData
}
```

For mutable per-record fields, pass a `delta` parameter and gate writes inside `data`. See the full pattern (including dynamic databases and pair relations) in `InkPatterns.md`.

## Common Helper Functions

These patterns appear in most inkle projects:

```ink
// Clamp a stat
=== function harm(x) ===
    { stamina < x:
        ~ stamina = 0
    - else:
        ~ stamina = stamina - x
    }

// Alter by delta (inline-friendly)
=== function alter(ref x, k) ===
    ~ x = x + k

// Check if just visited
=== function came_from(-> x) ===
    ~ return TURNS_SINCE(x) == 0

// Change a list property cleanly
=== function changeStateTo(ref stateVar, newState) ===
    ~ stateVar -= LIST_ALL(newState)
    ~ stateVar += newState
```

---

## Compiler Warnings to Know

| Situation                                     | Fix                           |
| --------------------------------------------- | ----------------------------- |
| Flow runs out without `-> END` or choice      | Add `-> END` or `-> DONE`     |
| Thread ends without content                   | Add `-> DONE`                 |
| Ambiguous list value (two lists share a name) | Use `ListName.value` syntax   |
| Loose end in tunnel                           | Ensure all paths reach `->->` |

## Mixing Weave and Conditionals

The compiler decides whether a gather point is "drop-through" or "collect-after-choices" at *compile time*, not at runtime, by looking for any choices in the knot. The moment any non-weave choice exists, gathers stop being harmless and will halt the flow when no choice was actually made.

```ink
=== conversation ===
<- talk_about_lemons
<- talk_about_roses
{ talked_about_lemons && talked_about_roses:
    * "Perhaps it's time to talk about the murder?" -> talk_about_murder
}

- -> gamewide_chat   // unreachable if the conditional choice doesn't fire
```

If both list flags are unset, no choices appear — but the bare `-` is treated as a gather (because *some* choice exists in the knot), so flow stops there and `gamewide_chat` is never reached.

**Fixes:** thread the conditional block in too (`<- conditional_choice`); or move the conditional choices into a separate stitch; or remove the gather. As a rule, if you have non-weave choices in a knot, every later flow-step needs to be explicitly diverted, not gathered.
