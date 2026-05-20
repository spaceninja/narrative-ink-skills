---
name: ink-style
description: Applies an opinionated set of Ink code formatting conventions to .ink files or ```ink code blocks in markdown. A Prettier-style formatter — whitespace/structure only, no semantic changes. Use when the user asks to format, clean up, or standardize Ink code style, or when editing Ink samples in docs.
---

# Ink Style Formatter

A non-destructive formatter for Ink code. Applies consistent indentation, spacing, and structural conventions without changing program semantics.

The full rule reference lives in [rules.md](rules.md). The formatter implementation lives in [format-ink.py](format-ink.py).

## When to invoke

- User asks to "format", "clean up", "prettify", or "standardize" Ink code
- User invokes `/narrative-ink:ink-style` or similar
- Editing Ink code samples in `.md` files where consistency matters
- Reviewing a PR that touches multiple Ink blocks with inconsistent style

Do NOT invoke when the user wants semantic changes (refactors, bug fixes, new features). This skill only changes whitespace and surface structure.

## How to apply

Run the bundled `format-ink.py` script — it lives in this skill's directory, next to this `SKILL.md`. It accepts `.ink` files (formatted whole) or `.md` files (only ```ink fenced blocks are touched; surrounding prose is left alone).

```bash
python3 format-ink.py PATH/TO/FILE       # format in place
python3 format-ink.py --check PATH       # print diff, exit 1 if changes needed
python3 format-ink.py --stdout PATH      # print formatted output to stdout
```

After formatting, run the verifier (below) before committing. Then report what changed to the user.

## Verification

Always verify the formatter didn't change compiled output:

```bash
python3 format-ink.py --verify-blocks PATH
```

For a `.md` file, this extracts each ```ink block, scaffolds it as a compilable snippet, compiles both the original and the formatted version with `inkjs-compiler`, and compares JSON. For a `.ink` file, it compiles the whole file before and after. Per-block outcomes:

- **PASS** — both compile, JSON identical
- **FAIL** — JSON differs, or formatter broke a compiling block (investigate before committing)
- **SKIP** — both fail to compile (snippet references functions/knots defined in another block; can't verify in isolation, but the formatter didn't make it worse)
- **WARN** — formatter "fixed" a compile error (surprising; investigate)

The verifier needs `inkjs-compiler`. It searches `$INKJS_COMPILER`, `$PATH`, and `./node_modules/.bin/inkjs-compiler`. Install it with `npm install inkjs` if it isn't already available.

## Non-destructive principle

The guiding rule: modify whitespace only where it provably cannot affect compiled output. Preserve everything else verbatim. See [rules.md](rules.md#guiding-principle) for the full statement.

The formatter changes:
- Indentation (natural alignment, see rules.md §1)
- Spacing around operators in code lines (`~`, `,`, `->`, before `(` in function calls)
- Whitespace inside `{...}` only when the braces contain a pure expression (no `:` and no `|`)
- Single space after `//` in line comments

The formatter does NOT change:
- Anything inside `{...}` when the braces contain `:` or `|` — content is rendered
- Choice text inside `[...]` or the surrounding choice line — rendered
- Tag whitespace (`#tag`, `# tag`, `#tag: value` all preserved as written)
- Variable names, function names, knot/stitch names
- Order of declarations, choices, or branches
- Anything outside ```` ```ink ```` blocks in markdown files

## Test fixtures

Two canonical fixtures live in `test-fixtures/`:

- `indentation-cases.ink` — covers L1–L5 nesting, switches, conditionals, knots, functions, stitches, tags, glue, and other edge cases
- `crime-scene-formatted.ink` — Joseph Humfrey's "Long example: crime scene" from inkle's [Writing with ink](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md) tutorial, fully formatted

Both are idempotent under the formatter: re-running produces no changes.
