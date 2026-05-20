---
name: ink-testing
description: Conventions for testing an Ink interactive fiction game with inkjs and vitest — how to write testable Ink code, when and how to write unit and integration tests, and what test helpers to set up. Use when writing or modifying tests, adding test coverage, or when a gameplay interaction warrants a new test.
---

# Testing an Ink Game

Test Ink source by compiling it with [inkjs](https://github.com/y-lohse/inkjs) and running assertions in a JavaScript test runner such as vitest. These conventions cover how to structure Ink code for testability, when to write each type of test, and what test helpers to set up.

## Write testable Ink code

Prefer extracting logic into named `=== function` blocks over embedding it inline in knot bodies. Inline logic can only be exercised through integration tests; extracted functions can be unit-tested directly and cheaply.

**Prefer this:**

```ink
=== function can_afford_fuel(fuel_amount)
~ return PlayerBankBalance >= FLOOR(fuel_amount * get_fuel_price(here))

= fuel_station
+ {can_afford_fuel(ShipFuelCapacity - ShipFuel)} [Fill it up] -> buy_fuel(...)
```

**Over this:**

```ink
= fuel_station
+ {PlayerBankBalance >= FLOOR((ShipFuelCapacity - ShipFuel) * get_fuel_price(here))} [Fill it up] -> buy_fuel(...)
```

When encountering existing inline logic that is complex enough to warrant testing, refactor it into a function.

## Writing unit tests for Ink functions

Whenever a new Ink function is added or an existing one is changed, add a corresponding unit test (e.g. under `tests/unit/`). Use `story.EvaluateFunction()` to call the function directly:

```js
// Pass list values using the createListItem() helper
const result = story.EvaluateFunction('get_cargo_pay', [
	createListItem(story, 'AllCargo.003_Water'),
	14,
]);
expect(result).toBe(1680);
```

Good candidates for unit tests (in order of priority):

- **Pure math functions** — price, cost, duration, or score calculations
- **Data lookups** — table-style functions that map a key (often a LIST item) to a value
- **Boolean predicates** — functions that answer a yes/no question about game state
- **Recursive list utilities** — functions that fold, filter, or sample over a LIST

## Suggesting integration tests

When a complex gameplay interaction is added or changed, suggest adding an integration test (e.g. under `tests/integration/`). Good candidates:

- A new gating check that blocks or unblocks a choice
- A new action that mutates global variables
- A new branch whose path depends on game state

Integration tests compile the story, advance it, select choices, and assert on the resulting state. Drive the story with the inkjs API (`story.currentChoices`, `story.ChooseChoiceIndex()`) and the `continueToNextChoice()` helper:

```js
const story = createStory();
continueToNextChoice(story); // advance to the first choice point

// pick a choice by matching its text, then advance again
const rest = story.currentChoices.findIndex((c) => c.text === 'Rest');
story.ChooseChoiceIndex(rest);
continueToNextChoice(story);

expect(story.variablesState['Health']).toBe(100);
```

## Test helpers

Set up a shared helper module (e.g. `tests/helpers/story.js`) that every test imports. It should provide factory functions like these:

- `createStory()` — compiles `.ink` source fresh; call once per test or in `beforeAll`
- `createListItem(story, 'ListName.ItemName')` — constructs the `InkList` value representing a single LIST item (needed to cross the JS↔Ink boundary)
- `createListUnion(story, ...names)` — constructs a multi-item `InkList` by unioning list-item values together
- `continueToNextChoice(story)` — advances the story until it blocks on a choice point or ends; returns the concatenated output text (usually discarded)

The list helpers matter because inkjs offers no convenient way to construct an `InkList` argument from JavaScript — passing LIST values into `EvaluateFunction()` otherwise means reaching into runtime internals.

## Performance

`createStory()` compiles the full Ink source and is the most expensive operation in tests. Keep these guidelines in mind to avoid CI timeouts:

- **Reuse story instances in loops.** For statistical or iteration-based tests, create the story once, then use `story.ResetState()` to reset all runtime state between iterations. Each reset is cheap; compilation is not.
- **Early-exit when possible.** For tests like "verify at least N distinct outcomes", break out of the loop as soon as the condition is met rather than running all iterations.
- **Keep iteration counts reasonable.** 50-100 iterations is fine when reusing a single story instance.

```js
// Good: one story, many iterations
const s = createStory();
for (let i = 0; i < 30; i++) {
	s.ResetState();
	s.EvaluateFunction('pick_random_event');
	// ... assert ...
	if (conditionMet) break; // early exit
}

// Bad: new story per iteration (causes CI timeouts)
for (let i = 0; i < 30; i++) {
	const s = createStory(); // compiles every time!
	// ...
}
```
