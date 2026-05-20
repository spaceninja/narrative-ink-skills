# Ink Style Rules

The complete rule reference for the [ink-style](SKILL.md) skill.

## Guiding principle

**Modify whitespace only where it provably cannot affect compiled output. Preserve everything else verbatim.**

In Ink, the same delimiters often contain both structural and rendered content. `{cond}` is a pure expression — whitespace inside has no effect. `{cond: text}` mixes them — anything after `:` is rendered to the player. `[text]` in a choice is rendered. Tags `#tag` are rendered (the runtime decides what to do with them). Sequences `{a|b|c}` are all-content. When in doubt, preserve.

The JSON-diff verification (see [SKILL.md](SKILL.md)) is the final authority: if formatting changes the compiled JSON, the change is destructive and must be reverted.

## Table of contents

1. [Indentation](#1-indentation) — the most important section
2. [Block declarations](#2-block-declarations)
3. [Choices and gathers](#3-choices-and-gathers)
4. [Conditionals](#4-conditionals)
5. [Operators and punctuation](#5-operators-and-punctuation)
6. [Variables and lists](#6-variables-and-lists)
7. [Comments](#7-comments)

---

## 1. Indentation

### 1.1 Natural alignment under markers

Indentation is **natural alignment**, not a fixed indent unit. Content under a choice (`*`, `+`) or a switch branch (`-` inside `{...}`) sits at the column where the choice/branch text naturally begins — `marker_col + marker_length + 1` (the column after `marker + space`).

Nested markers are placed at the parent's natural content column. No tabs.

This matches the style used in inkle's canonical [Writing with ink](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md) documentation.

**Gathers don't introduce indent.** A gather marker `-` outside any `{...}` is a label that collapses the flow back to its own column. Content that follows a gather sits at the **gather's column**, not at natural alignment past it.

```ink
~ temp count = 0       // col 0
- (top_of_loop)        // col 0 — L0 gather
Give me a {count}!     // col 0 — content after gather stays at gather's col
- (bottom_of_loop)     // col 0
~ count++              // col 0
```

The same applies to deeper-level gathers: an L2 gather `- -` at col 2 has following content at col 2 (not col 6). Inside a switch the `-` is a branch, not a gather, and natural alignment applies as normal.

### 1.2 The natural alignment table

For choice markers (`*`, `+`, `* *`, etc.):

| Level | Marker | Marker col | Content col |
|---|---|---|---|
| L1 | `*` (1 char) | 0 | 2 |
| L2 | `* *` (3 chars) | 2 | 6 |
| L3 | `* * *` (5 chars) | 6 | 12 |
| L4 | `* * * *` (7 chars) | 12 | 20 |
| L5 | `* * * * *` (9 chars) | 20 | 30 |

General formula: at nesting level L, marker is at column `L × (L − 1)`, content is at column `L × (L + 1)`.

Gathers sit at the same marker column as a peer choice (so an L2 gather `- -` is at col 2), but content following the gather stays at that **marker column**, not the content column (see §1.1).

For switch branches inside `{...}`, the branch marker is `-` (1 char). Branch content is at branch marker col + 2.

### 1.3 Knot/function/stitch body is not indented from its header

Body code starts at column 0 directly under the header.

```ink
=== murder_scene ===
The bedroom. This is where it happened.   // col 0
- (top)
* [The bed...]
  The bed was low to the ground.          // L1 content at col 2
```

### 1.4 Strip trailing whitespace

Every line. No exceptions.

---

## 2. Block declarations

### 2.1 Knot header: `=== name ===`

Trailing equals **required**. Applies to bare knots and parameterized knots used like tunnels.

```ink
=== murder_scene ===
=== cheerleader_invite() ===
```

### 2.2 Function header: `=== function name(args)`

Trailing equals **forbidden** on pure functions.

```ink
=== function pop(ref list)
=== function reach(statesToSet)
```

### 2.3 Stitch header: `= name`

Single equals, no trailing. No parentheses unless parameterized.

```ink
= operate_lamp
= compare_prints(-> backto)
```

### 2.4 One blank line before each knot/stitch/function declaration

Separates blocks visually. No blank line between a block comment and the declaration it documents.

```ink
~ end of previous block

/*

    Talk to Cheerleader

*/
=== talk_to_cheerleader ===
```

---

## 3. Choices and gathers

### 3.1 Marker placement

Markers are placed at the parent's natural content column (see §1.2 table). L1 at col 0, L2 at col 2, L3 at col 6, L4 at col 12, L5 at col 20.

Gathers and choices at the **same level** sit at the **same column**:

```ink
* (dobed) [The bed...]
  The bed was low to the ground.
  - - (bedhub)            // L2 gather at col 2
  * * [Lift the bedcover] // L2 choice at col 2 — same column
      I lifted back the bedcover.   // L2 content at col 6
  - - -> bedhub           // L2 gather at col 2
```

### 3.2 Nested marker style: spaced asterisks

Use `* *` not `**`. Same for `+ +`, `- -`, `* * *`, etc.

### 3.2a Single space between marker tokens and content

`* text`, `* * text`, `* (label) text`, `- (label) content` — single space between marker tokens, single space before content. No multi-space padding.

```ink
*   "Hi."          // wrong — multi-space padding
* "Hi."            // right — single space
-   (gather)       // wrong
- (gather)         // right
```

### 3.3 Content layout: single-line if ≤80 chars, else drop

```ink
* [Lift the bedcover]
  I lifted back the bedcover.     // L1 content at col 2

* {darkunder && bedroomLightState ? on_floor && bedroomLightState ? on}
  [Look under the bed]            // condition wrapped → bracket text drops to next line at col 2
  I peered under the bed.
```

The bracket text on a wrapped line sits at the natural content column (per §1.2).

### 3.4 Single space before `->` divert; no padding alignment

```ink
* [Foo] -> bar
* [Longer foo] -> baz   // no padding to align arrows
```

---

## 4. Conditionals

Ink has several conditional/sequence forms. The formatter rule for whitespace inside `{...}` depends on whether any content position exists inside.

### 4.1 Whitespace inside `{...}`

**Strip interior whitespace only if the braces contain a pure expression** — no top-level `:` and no top-level `|`.

| Form | Top-level `:`? | Top-level `\|`? | Whitespace inside |
|---|---|---|---|
| `{my_var}` print | no | no | **strip** |
| `{cond}` choice gate | no | no | **strip** |
| `{func(x)}` call | no | no | **strip** |
| `{cond: text}` inline cond | yes | no | **preserve** (text is rendered) |
| `{a\|b\|c}` sequence | no | yes | **preserve** (options are rendered) |
| `{shuffle: a\|b\|c}` | yes | yes | **preserve** |

Examples:

```ink
// pure expression — strip
{ my_var }              → {my_var}
* { Inventory ? cane } [Knock it...]   → * {Inventory ? cane} [Knock it...]
{ CountContaining(LIST_ALL(x), "y") }  → {CountContaining(LIST_ALL(x), "y")}

// has : or | — preserve verbatim
{ x > 0: positive }     stays { x > 0: positive }
{cond: A | B }          stays {cond: A | B }
{ a | b | c }           stays { a | b | c }
```

The rationale: whitespace inside a pure-expression `{...}` has no effect on compiled output (verified by JSON diff). Whitespace inside an expression that contains rendered content — either after a `:` or as options separated by `|` — may affect output, so we preserve the whole interior to keep the rule simple and safe.

### 4.2 Switch form: opening `{` on its own line

Branch markers `- cond:` align with the opening `{`. Branch content sits at the branch marker's natural alignment (col + 2 for the 1-char `-` marker).

```ink
{
- not x:
  ~ return false
- not reached(x):
  ~ temp chain = LIST_ALL(x)
  ~ knowledgeState += statesGained
- else:
  ~ return false || reach(statesToSet)
}
```

### 4.3 Compact switch: `{cond:` opens with first branch inline

Simple if/else only — only `- else:` is allowed as an additional branch.

```ink
{bedroomLightState ? on:
  <> The bulb fell dark.
  ~ bedroomLightState += off
- else:
  <> Light spilled in.
  ~ bedroomLightState += on
}
```

Same indentation rules as §4.2 — branches align with `{`, content at branch col + 2.

Both surface forms (§4.2 and §4.3) are valid author choices. The formatter respects which one was written; it does not convert between them.

### 4.4 Line comments inside a switch align with the branch markers

When a switch has explicit `-` branches, line comments (`// ...`) inside that switch sit at the same column as the `-` branch markers — i.e. at the opening `{`'s column — not at branch-content depth.

```ink
{shuffle:
// some options guarded by conditionals
- {condition:
    ~ return -> knot_A
  }
- {condition:
    ~ return -> knot_B
  }
}
```

A switch with no `-` branches (just unconditional content inside `{cond: ... }`) is the exception: comments there stay at the regular content position alongside the code they describe.

```ink
{TURNS_SINCE(link) >= 0:
  {TURNS_SINCE(marker) == -1:
    ~ return true
  }
  // did you see link fewer turns ago than marker?
  ~ return TURNS_SINCE(link) < TURNS_SINCE(marker)
}
```

---

## 5. Operators and punctuation

### 5.1 Function call: no space before paren

```ink
pop(list)               // yes
pop (list)              // no
move_to_supporter(x, y) // yes
```

### 5.2 Single space after `~`, `//`, `->`, `=`, `,`

Codifies universal practice.

```ink
~ temp x = 5            // single space after ~ and around =
// comment              // single space after //
-> knot                 // single space after ->
LIST L = a, b, c        // single space after ,
```

### 5.3 Tags: preserve verbatim

To the Ink compiler, the entire string after `#` is the tag string. Inky's web template happens to `.trim()` and split on `:`, but that's runtime convention — other runtimes see the literal string. Any whitespace edit inside a tag changes the tag string and therefore the output.

The formatter does **not** touch any whitespace between `#` and end of tag.

```ink
# tag           // preserved as written
#tag            // preserved as written
#CLASS: end     // preserved as written
# CLASS : end   // preserved as written (whether you like it or not)
```

---

## 6. Variables and lists

### 6.1 Long LIST declarations wrap at 80 chars

Wrap with 4-space continuation indent. Compiles cleanly (verified).

```ink
LIST Dice =
    MeA1 = 11, MeA2, MeA3, MeA4,
    MeB1 = 21, MeB2, MeB3, MeB4,
    ThemA1 = 61, ThemA2, ThemA3, ThemA4,
    ThemB1 = 71, ThemB2, ThemB3, ThemB4
```

Most LISTs fit on one line — only wrap when necessary.

### 6.2 Blank lines between VAR groups

Author's discretion. If grouping exists in source, preserve it.

```ink
// Character traits
VAR forceful = 0
VAR evasive = 0

// Inventory
VAR teacup = false
VAR gotcomponent = false
```

---

## 7. Comments

### 7.1 Decorative section headers: block-comment form

```ink
/*

    System: inventory

*/
```

Pattern: `/*`, blank line, indented text (4 spaces), blank line, `*/`. Use for section headers within a file.

**Convert** legacy line-comment banners to this form:

```ink
// in:
//
// System: inventory
//

// out:
/*

    System: inventory

*/
```

### 7.2 Single-line comments: single space after `//`

```ink
~ reach(statesToSet) // single space after //
```

No padding-alignment of trailing comments.

### 7.3 TODOs use Ink's built-in syntax

Bare `TODO:` at column 0 (Ink's compiler indexes these and displays them).

```ink
TODO: handle the case where the player has no cane
```

Not `// TODO:` — that's a regular comment.

---

## Summary: what changes vs. what doesn't

**Changes (formatter applies):**
- Indentation per §1
- Block-comment banners (§7.1)
- Function header trailing equals (§2.2)
- Whitespace inside pure-expression `{...}` only (§4.1)
- Padding around operators, after `~`, around `=`, after `,`, before `(` in function calls (§5)
- Marker token spacing (`* *`, `- -`) and marker→content single space (§3.2, §3.2a) — verified non-destructive
- Single space after `//` in line comments (§7.2)

**Does NOT change (would alter compiled output):**
- Anything inside `{...}` when the braces contain `:` or `|` — content is rendered
- Choice text inside `[...]` — rendered in choice display
- Choice prefix and suffix text **outside** `[...]` on a choice line — rendered
- Tag whitespace from `#` to end of tag (§5.3)
- Narrative text on any content line
- Names of knots, stitches, functions, variables, lists
- Order of declarations, choices, or branches
