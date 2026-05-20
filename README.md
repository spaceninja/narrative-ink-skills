# narrative-ink-skills

Agent skills for [Ink](https://www.inklestudios.com/ink/), inkle's narrative
scripting language for interactive fiction.

This repository is a Claude Code plugin marketplace containing a single plugin,
`narrative-ink`, which bundles three skills:

| Skill | What it does |
| --- | --- |
| `syntax` | A condensed syntax reference for the Ink language — knots, stitches, choices, diverts, variables, lists, threads, tunnels, and common gotchas. Consult it when writing or reviewing `.ink` files. |
| `style` | A Prettier-style formatter for `.ink` files and ` ```ink ` code blocks in markdown. Whitespace and structure only — no semantic changes. |
| `testing` | Conventions for testing an Ink story compiled with [inkjs](https://github.com/y-lohse/inkjs) and run under a JS test runner such as [vitest](https://vitest.dev/) — how to structure Ink for testability and when to write unit vs. integration tests. |

The skills follow the open [Agent Skills](https://agentskills.io) standard, so they
also work in Cursor, Codex, Gemini CLI, and other agentskills.io-compatible agents.

## Install in Claude Code

```text
/plugin marketplace add spaceninja/narrative-ink-skills
/plugin install narrative-ink@narrative-ink-skills
```

Once installed, the skills are namespaced under the plugin and invoked as
`/narrative-ink:syntax`, `/narrative-ink:style`, and `/narrative-ink:testing`.
Claude also activates them automatically when a task involves `.ink` files.

To update later, run `/plugin marketplace update` followed by `/plugin update`.

## Install in other agents

The skills themselves are plain [Agent Skills](https://agentskills.io) — only the
`plugin.json` / `marketplace.json` wrapper is Claude Code-specific. For any other
agentskills.io-compatible agent, copy the skill folders from
`plugins/narrative-ink/skills/` into your agent's skills directory:

```text
plugins/narrative-ink/skills/syntax/
plugins/narrative-ink/skills/style/
plugins/narrative-ink/skills/testing/
```

The `style` skill includes a Python 3 formatter (`format-ink.py`); it has no
third-party dependencies, but its `--verify-blocks` mode needs `inkjs-compiler`
on your `PATH`.

## Attribution

The `style` skill's test fixture `crime-scene-formatted.ink` is a formatted copy of
the "Long example: crime scene" from inkle's open-source
[Writing with ink](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md)
tutorial.

## License

[MIT](LICENSE) © 2026 Scott Vandehey
