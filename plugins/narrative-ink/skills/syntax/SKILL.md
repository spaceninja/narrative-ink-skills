---
name: syntax
description: Provides syntax reference and authoring guidance for the Ink scripting language (inkle/ink). Use when writing, editing, or reviewing .ink files, when asked about Ink syntax, knots, stitches, choices, diverts, variables, lists, or any Ink language feature.
---

# Ink Language Syntax

Ink is a narrative scripting language for interactive stories. Files use the `.ink` extension.

## Core Building Blocks

### Content & Comments

```ink
Plain text is printed as-is.

// Single-line comment (ignored by compiler)
/* Multi-line comment */
TODO: Compiler prints this as a reminder
```

### Tags

Tags are metadata attached to text. The compiler passes them through to the runtime; the player never sees them.

```ink
#author: Joseph Humfrey                   // global tag (at top of file, outside any knot)
#title: My Wonderful Ink Story

A line of normal text. #blue              // line tag

=== forest ===
#location: Germany                        // knot tag (applies until first stitch/content)
#overview: munich.ogg

* [Wait] #unclickable                     // choice tag
The price is {gold}. # cost:{gold}        // dynamic tag (expression in braces)
```

Tags placed on the lines immediately after a knot header (before any content or stitch) are treated as knot tags. Global tags appear at the top of the file, outside any knot, and are queryable by the runtime before the story begins.

### Choices

```ink
* Once-only choice (disappears after selected)
+ Sticky choice (always available)
* [Bracketed text] suppresses choice text from output
* Prefix [only in choice] suffix in output   // before=both, inside=choice only, after=output only
```

### Knots & Stitches

```ink
=== knot_name ===                  // top-level section; === name is fine too
= stitch_name                      // sub-section inside a knot
=== knot_name(arg, ref var) ===    // knots can take parameters; `ref` = pass by reference
```

Parameters are scoped like temporary variables: they exist for the duration of that knot/stitch.

### Diverts

```ink
-> knot_name           // jump to knot
-> knot_name.stitch    // jump to stitch
-> END                 // end the story
-> DONE                // end a thread (not the whole story)
<>                     // glue: suppress line break
```

### Gathers

```ink
- Gather point: rejoins branching flow
-- Nested gather (level 2)
- (label) Named gather: can be diverted to or tested
```

## Variables & Logic

```ink
VAR gold = 0              // global variable (int, float, string, bool, or divert)
CONST MAX = 100           // constant
~ temp x = 5              // temporary variable (scoped to current stitch)

~ gold = gold + 7         // assignment
~ gold++                  // increment
```

### Strings

Strings can be concatenated directly or built via interpolation. The interpolated form is more powerful because the contents are evaluated as Ink:

```ink
~ name = first_name + " " + second_name
~ name = "{first_name} {second_name}"
~ title = "the {~marvellous|mysterious} {second_name}"
~ surname += "Darcy"      // append works; subtracting strings does not
```

### Conditionals

```ink
{ condition: text if true | text if false }
{ condition: text if true }

{ x > 0:
    ~ y = x - 1
- else:
    ~ y = x + 1
}

{
    - x == 0: zero
    - x > 0: positive
    - else: negative
}
```

Logical operators support both keyword and symbol forms: `and`/`&&`, `or`/`||`, `not`/`!`. Prefer the keyword forms — `{!text}` is ambiguous with a once-only alternative and can confuse the compiler.

```ink
{ not visited_paris and (has_ticket or has_passport): ... }
```

### Switch Blocks

A value-driven switch is a distinct form from extended if/else:

```ink
{ x:
- 0:     zero
- 1:     one
- 2:     two
- else:  lots
}
```

### Conditional Choices

```ink
* { condition } [Choice only shown if condition is true]
* { not visited_paris } [Go to Paris] -> visit_paris
+ { visit_paris } [Return to Paris] -> visit_paris
```

## Variable Text

```ink
{one|two|three}          // sequence: shows next each visit, sticks on last
{&Monday|Tuesday|Wed}    // cycle: loops
{!once|twice|thrice}     // once-only: blank after exhausted
{~Heads|Tails}           // shuffle: random

{variable_name}          // print variable value
```

## Functions

```ink
=== function my_func(a, b) ===
    ~ return a + b

~ result = my_func(3, 4)

=== function alter(ref x, k) ===   // ref = pass by reference
    ~ x = x + k
```

Functions cannot contain stitches, choices, or diverts.

## Tunnels

```ink
-> crossing_the_date_line ->    // run sub-story, then return
->->                            // exit tunnel (return to caller)
-> tunnel_a -> tunnel_b -> done // chain tunnels
```

## Threads

```ink
<- thread_knot             // fork in content from another knot
-> DONE                    // mark intentional end of a thread
```

## Lists (State Tracking)

```ink
LIST State = off, (on), standby    // brackets = initial value; the LIST also creates a variable named State
VAR device = on                    // separate variable, initialised to a list item

~ device = on              // set single value
~ device++                 // advance to next value
~ device += on             // add value (multi-valued)
~ device -= off            // remove value
~ device = ()              // clear

{ device == on }           // equality
{ device ? on }            // containment ( `has` is the keyword form)
{ device !? off }          // does not contain (`hasnt` is the keyword form)
{LIST_COUNT(device)}       // number of active values
{LIST_MIN(device)}         // lowest active value
{LIST_MAX(device)}         // highest active value
{LIST_ALL(device)}         // all possible values
{LIST_RANDOM(device)}      // a random active value (empty list if device is empty)
{LIST_VALUE(on)}           // integer value of a list item (1-indexed by default)
{State(2)}                 // construct an item from its integer value
```

List values are conceptually enums and are 1-indexed by default. Custom numerical values can be assigned: `LIST primes = two = 2, three = 3, five = 5`.

## Read Counts & Game Queries

```ink
{ knot_name }              // true if knot has been visited
{ knot_name > 2 }          // visited more than 2 times
CHOICE_COUNT()             // number of choices created so far in this chunk
TURNS()                    // total turns since game began
TURNS_SINCE(-> knot)       // turns since knot visited; -1 = never seen
RANDOM(1, 6)               // random integer, inclusive
SEED_RANDOM(42)            // seed for deterministic testing
```

## Validating Ink Code

After editing a `.ink` file, validate it by compiling. Many projects expose this as a script (e.g. `npm run lint`); if no script exists, run the compiler directly on the entry-point file — it will recursively compile all `INCLUDE`d files:

```bash
inkjs-compiler path/to/entry.ink
```

`TODO:` lines are informational and can be ignored. Any `ERROR:` line must be fixed before the change is considered done.

## Common Errors and Gotchas

- **`~` must be on its own line** — never inline inside `{ }`. Use a multi-line block:

  ```ink
  // Wrong:
  { condition: ~ return true }

  // Correct:
  { condition:
      ~ return true
  }
  ```

- **Functions cannot divert or offer choices.** Use recursion for loops; use knots/stitches/tunnels when narrative flow is needed.
- **Every function path must terminate** with `~ return` or fall through to one.
- **VAR list initialisation needs parens** for multi-valued lists: `VAR active = (A, B, C)`, not `VAR active = A, B, C`.
- **Don't mix the two conditional syntaxes.** The simple form has the condition inline and only supports `- else:` as an extra branch (`{ cond: ... - else: ... }`). The extended form puts `{` on its own line and uses `- condition:` for *every* branch including the first. A simple opening combined with an extended-style `- condition:` branch is a compile error.
- **Threads (`<-`) are not tunnels (`-> ... ->`).** A stitch entered via a thread cannot use `->->` to return — there's no call stack. Every branch must divert explicitly. To suppress a thread's choices conditionally, gate them with `+ { condition }` rather than trying to early-return.
- **Integer division has higher precedence than multiplication.** `a * b / c` evaluates as `a * (b / c)`, which truncates early. For example, `5 * 3 / 2` is `5` (because `3 / 2 = 1`), not `7`. Force the order with parentheses: `(a * b) / c`.

## Include Files

```ink
INCLUDE other_file.ink     // always at top of file, outside knots
```

## Common Patterns

**Loop with fallback:**

```ink
=== find_help ===
* The woman in the hat[?] pushes you aside. -> find_help
* The man with the briefcase[?] ignores you. -> find_help
* ->
    You give up.
    -> END
```

**Question hub (re-entrant):**

```ink
- (opts)
    * [Ask about X] ... -> opts
    * [Ask about Y] ... -> opts
    * { opts > 1 } [Done talking] -> continue
- -> opts
```

**Parameterised knot as tunnel:**

```ink
-> generic_sleep(-> wake_up) ->

=== generic_sleep(-> waking) ===
You drift off...
-> waking
```

## Additional Reference

For complete documentation on advanced list operations, multi-list state machines, threads, and the full weave syntax, see [reference.md](reference.md).
