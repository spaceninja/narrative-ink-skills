#!/usr/bin/env python3
"""
Ink code formatter.

Applies an opinionated set of Ink code formatting conventions. See rules.md for
the full rule reference; the guiding principle is to modify whitespace only where
it provably cannot affect compiled output.

Usage:
    format-ink.py FILE              Format FILE in place.
    format-ink.py --check FILE      Print diff to stdout; exit 1 if changes needed.
    format-ink.py --stdout FILE     Print formatted output to stdout, don't write.

FILE may be a .ink file (formatted whole) or a .md file (only ```ink fences are
formatted; surrounding markdown is left untouched).
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Iterator


class LineType(Enum):
    BLANK = "blank"
    KNOT = "knot"                    # === name === or === function name(args)
    STITCH = "stitch"                # = name
    DECLARATION = "declaration"       # VAR / CONST / LIST / INCLUDE / EXTERNAL
    MARKER = "marker"                 # * / + / - line, possibly nested (* *, - -, etc.)
    CODE = "code"                     # ~ expression
    DIVERT = "divert"                 # -> target line on its own
    BRACE_OPEN = "brace_open"         # { alone on a line
    BRACE_CLOSE = "brace_close"       # } alone on a line
    COMPACT_SWITCH = "compact_switch" # {cond: opening a multi-line if/else block
    LINE_COMMENT = "line_comment"     # // comment on its own line
    BLOCK_COMMENT = "block_comment"   # /* ... */ or any line within
    TODO = "todo"                     # TODO: ... at col 0
    CONTENT = "content"               # everything else (narrative text)


@dataclass
class Token:
    """One classified source line.

    Attributes:
        type: line classification
        raw: original line text (no trailing newline)
        indent: count of leading whitespace characters in the original
        body: the line with leading and trailing whitespace stripped
        marker_depth: for MARKER, the nesting depth (1 = L1, 2 = L2, ...)
        marker_char: for MARKER, the marker character ('*', '+', or '-')
        marker_rest: for MARKER, the text after the marker tokens (excluding the
            separating whitespace), e.g. for `* * (label) text` this is `(label) text`
    """

    type: LineType
    raw: str
    indent: int
    body: str
    marker_depth: int = 0
    marker_char: str = ""
    marker_rest: str = ""


def _parse_marker(stripped: str) -> tuple[int, str, str] | None:
    """If STRIPPED begins with one or more marker tokens, return (depth, char, rest).

    A marker token is a single `*`, `+`, or `-` followed by whitespace (or end of line).
    All marker tokens on a single line must share the same character. The leading
    `-` in `->` (divert) is not a marker.

    Returns None if STRIPPED does not begin with a marker.
    """
    if not stripped:
        return None
    char = stripped[0]
    if char not in "*+-":
        return None
    # Reject `->` (divert) — `-` followed immediately by non-whitespace.
    if len(stripped) > 1 and stripped[1] not in " \t":
        return None

    depth = 0
    pos = 0
    while pos < len(stripped) and stripped[pos] == char:
        # Each marker char must be followed by whitespace or end-of-line.
        if pos + 1 < len(stripped) and stripped[pos + 1] not in " \t":
            break
        depth += 1
        pos += 1
        while pos < len(stripped) and stripped[pos] in " \t":
            pos += 1
    if depth == 0:
        return None
    return depth, char, stripped[pos:]


def _classify(line: str, in_block_comment: bool) -> tuple[Token, bool]:
    """Classify LINE; return (token, new_in_block_comment)."""
    indent = len(line) - len(line.lstrip(" \t"))
    stripped = line.strip()

    # Inside a multi-line block comment, every line (including the closer) is BLOCK_COMMENT.
    if in_block_comment:
        next_state = "*/" not in stripped
        return (
            Token(LineType.BLOCK_COMMENT, line, indent, stripped),
            next_state,
        )

    if not stripped:
        return Token(LineType.BLANK, line, 0, ""), False

    # Block comment open: `/*` may close on the same line (`/* foo */`) or span lines.
    if stripped.startswith("/*"):
        spans_lines = "*/" not in stripped[2:]
        return (
            Token(LineType.BLOCK_COMMENT, line, indent, stripped),
            spans_lines,
        )

    # Pure line comment.
    if stripped.startswith("//"):
        return Token(LineType.LINE_COMMENT, line, indent, stripped), False

    # Block declarations.
    if stripped.startswith("==="):
        return Token(LineType.KNOT, line, indent, stripped), False
    if stripped.startswith("= ") or stripped == "=":
        return Token(LineType.STITCH, line, indent, stripped), False

    # VAR / CONST / LIST / INCLUDE / EXTERNAL keywords at line start.
    first_word = stripped.split(None, 1)[0]
    if first_word in {"VAR", "CONST", "LIST", "INCLUDE", "EXTERNAL"}:
        return Token(LineType.DECLARATION, line, indent, stripped), False

    # TODO at column 0 (Ink compiler indexes these).
    if indent == 0 and stripped.startswith("TODO:"):
        return Token(LineType.TODO, line, indent, stripped), False

    # Brace-opening lines: `{` alone (multi-branch switch) or `{cond:` (compact if/else).
    # Detect by brace balance — if the line has more `{` than `}`, it opens a multi-line block.
    if stripped.startswith("{") and stripped.count("{") > stripped.count("}"):
        if stripped == "{":
            return Token(LineType.BRACE_OPEN, line, indent, stripped), False
        return Token(LineType.COMPACT_SWITCH, line, indent, stripped), False
    if stripped == "}":
        return Token(LineType.BRACE_CLOSE, line, indent, stripped), False

    # Code line (variable assignment, function call, return).
    if stripped.startswith("~"):
        return Token(LineType.CODE, line, indent, stripped), False

    # Divert line on its own (`-> target` or `->->`).
    if stripped.startswith("->"):
        return Token(LineType.DIVERT, line, indent, stripped), False

    # Marker line: choice, sticky choice, or gather.
    marker = _parse_marker(stripped)
    if marker is not None:
        depth, char, rest = marker
        return (
            Token(
                LineType.MARKER,
                line,
                indent,
                stripped,
                marker_depth=depth,
                marker_char=char,
                marker_rest=rest,
            ),
            False,
        )

    # Everything else is narrative content (including lines that begin with `{...}`
    # inline conditionals, lines with text, lines with tags appended, etc.).
    return Token(LineType.CONTENT, line, indent, stripped), False


def lex(source: str) -> list[Token]:
    """Tokenize SOURCE into a list of classified line tokens."""
    tokens: list[Token] = []
    in_block_comment = False
    # splitlines() drops the trailing newline; we lose final-newline info but that's
    # handled by the writer.
    for line in source.splitlines():
        token, in_block_comment = _classify(line, in_block_comment)
        tokens.append(token)
    return tokens


# ---------- Token-level normalizations (rules §3.4, §5, §7.2) ----------

# Strip whitespace before `(` in function calls: `func (x)` -> `func(x)`.
# Excludes Ink keywords/operators where `(` introduces a grouped expression.
_INK_PAREN_KEYWORDS = frozenset({"return", "not", "and", "or"})
_RE_PAREN_SPACE = re.compile(r"(\w+)[ \t]+\(")


def _strip_space_before_paren(body: str) -> str:
    def repl(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in _INK_PAREN_KEYWORDS:
            return m.group(0)
        return name + "("

    return _RE_PAREN_SPACE.sub(repl, body)

# Strip whitespace immediately before a comma: `a , b` -> `a, b`.
_RE_SPACE_BEFORE_COMMA = re.compile(r"[ \t]+,")

# Collapse comma-then-whitespace to comma-then-single-space, but only when there's
# a following non-space (don't add a trailing space at end of line).
_RE_COMMA_SPACE = re.compile(r",[ \t]*(\S)")

# Single space after a leading `~`.
_RE_TILDE_PREFIX = re.compile(r"^~[ \t]*")

# Single space after `//` in a comment; preserve `//` alone.
_RE_DSLASH_PREFIX = re.compile(r"^//[ \t]*")

# Single space after `->` at the start of a divert line.
_RE_DIVERT_PREFIX = re.compile(r"^->[ \t]*")

# Single space after VAR / CONST / LIST / INCLUDE / EXTERNAL keyword.
_RE_DECL_KEYWORD = re.compile(r"^(VAR|CONST|LIST|INCLUDE|EXTERNAL)[ \t]+")


def _normalize_code_body(body: str) -> str:
    """Normalize a `~ ...` code line."""
    body = _RE_TILDE_PREFIX.sub("~ ", body)
    body = _strip_space_before_paren(body)
    body = _RE_SPACE_BEFORE_COMMA.sub(",", body)
    body = _RE_COMMA_SPACE.sub(r", \1", body)
    return body


def _normalize_declaration_body(body: str) -> str:
    """Normalize a VAR / CONST / LIST / INCLUDE / EXTERNAL line."""
    body = _RE_DECL_KEYWORD.sub(lambda m: m.group(1) + " ", body)
    body = _strip_space_before_paren(body)
    body = _RE_SPACE_BEFORE_COMMA.sub(",", body)
    body = _RE_COMMA_SPACE.sub(r", \1", body)
    return body


def _normalize_divert_body(body: str) -> str:
    """Normalize a standalone `-> target` line.

    Preserves the tunnel-return operator `->->`, which must not have an
    interior space.
    """
    if body.startswith("->->"):
        return body
    return _RE_DIVERT_PREFIX.sub("-> ", body)


def _normalize_line_comment_body(body: str) -> str:
    """Normalize a `// ...` line comment. Preserves `//` alone."""
    if body == "//":
        return body
    return _RE_DSLASH_PREFIX.sub("// ", body)


def _normalize_brace_region(region: str) -> str:
    """Apply rules.md §4.1 to a complete `{...}` region.

    If the interior contains a top-level `:` or `|`, preserve verbatim — those
    separators mark content positions whose whitespace is rendered.

    Otherwise (pure expression like `{my_var}`, `{cond}`, `{func(x)}`), strip
    leading and trailing whitespace inside the braces.
    """
    if len(region) < 2 or region[0] != "{" or region[-1] != "}":
        return region
    interior = region[1:-1]
    depth = 0
    i = 0
    while i < len(interior):
        c = interior[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0:
            # `||` is the logical-OR operator, not a sequence pipe — skip past it.
            if c == "|" and i + 1 < len(interior) and interior[i + 1] == "|":
                i += 2
                continue
            if c in (":", "|"):
                return region
        i += 1
    return "{" + interior.strip() + "}"


def _normalize_braces_in_line(line: str) -> str:
    """Walk LINE and normalize every top-level `{...}` region."""
    result: list[str] = []
    i = 0
    while i < len(line):
        if line[i] != "{":
            result.append(line[i])
            i += 1
            continue
        # Find matching `}` (depth-aware).
        depth = 1
        j = i + 1
        while j < len(line) and depth > 0:
            if line[j] == "{":
                depth += 1
            elif line[j] == "}":
                depth -= 1
            j += 1
        if depth == 0:
            result.append(_normalize_brace_region(line[i:j]))
            i = j
        else:
            # Unmatched `{` (e.g. start of a multi-line block) — leave as-is.
            result.append(line[i])
            i += 1
    return "".join(result)


def _normalize_compact_switch_body(body: str) -> str:
    """Normalize a `{cond:` opener line (rules.md §4.1, §4.3).

    The whole line is structural — the condition expression sits between `{`
    and `:`, with no rendered content on this line. Strip the decorative
    whitespace just inside `{` and around `:`.
    """
    m = re.match(r"^\{\s*(.*?)\s*:\s*$", body, re.DOTALL)
    if not m:
        return body
    return "{" + m.group(1) + ":"


def normalize_tokens(tokens: list[Token]) -> list[Token]:
    """Apply per-token-type whitespace normalizations.

    Only touches tokens whose body is entirely structural/code — never narrative
    content, marker rests (which may contain rendered text), or knot/stitch
    headers (handled separately if at all).
    """
    out: list[Token] = []
    for tok in tokens:
        new_body = tok.body
        new_rest = tok.marker_rest
        if tok.type is LineType.CODE:
            new_body = _normalize_code_body(tok.body)
        elif tok.type is LineType.DECLARATION:
            new_body = _normalize_declaration_body(tok.body)
        elif tok.type is LineType.DIVERT:
            new_body = _normalize_divert_body(tok.body)
        elif tok.type is LineType.LINE_COMMENT:
            new_body = _normalize_line_comment_body(tok.body)
        elif tok.type is LineType.CONTENT:
            new_body = _normalize_braces_in_line(tok.body)
        elif tok.type is LineType.COMPACT_SWITCH:
            new_body = _normalize_compact_switch_body(tok.body)
        elif tok.type is LineType.MARKER:
            new_rest = _normalize_braces_in_line(tok.marker_rest)
        if new_body != tok.body or new_rest != tok.marker_rest:
            tok = replace(tok, body=new_body, marker_rest=new_rest)
        out.append(tok)
    return out


@dataclass
class Frame:
    """One indentation context on the indenter's stack.

    Kinds:
        "knot"   — knot/stitch/function body. Content sits at col 0.
        "marker" — a choice/gather/branch. Choice/branch content sits at natural
                   alignment (marker_col + marker_len + 1). Gather content sits
                   at marker_col (gathers don't introduce indent — see rules.md §1.1).
        "switch" — a {...} block opened by either BRACE_OPEN or COMPACT_SWITCH.
                   Branches go at brace_col; content inside (before any explicit
                   `- branch:`) goes at brace_col + 2.
    """

    kind: str
    base_col: int = 0           # for "knot": 0; for "switch": brace_col
    marker_depth: int = 0       # for "marker"
    marker_char: str = ""       # for "marker"
    marker_col: int = 0         # for "marker"
    marker_len: int = 0         # for "marker": chars in marker tokens, e.g. 3 for "* *"
    is_gather: bool = False     # for "marker": True iff `-` outside any switch
    has_branches: bool = False  # for "switch": True once a `-` branch has been seen

    @property
    def content_col(self) -> int:
        """Column where following text/code/switch should be emitted."""
        if self.kind == "marker":
            if self.is_gather:
                return self.marker_col
            return self.marker_col + self.marker_len + 1
        if self.kind == "switch":
            return self.base_col + 2
        return self.base_col  # knot

    @property
    def child_marker_col(self) -> int:
        """Column where a child marker (choice/gather/branch) should sit.

        Gathers don't push *content* right (see rules.md §1.1) but they DO
        retain their natural alignment for nested markers — an L2 gather under
        an L1 gather still belongs at col 2.
        """
        if self.kind == "marker":
            return self.marker_col + self.marker_len + 1
        return self.content_col


def _find_enclosing_switch(stack: list[Frame]) -> int | None:
    """Return the stack index of the enclosing switch frame, or None.

    Stops at the first "knot" frame (a switch cannot reach across a knot boundary).
    """
    for i in range(len(stack) - 1, -1, -1):
        if stack[i].kind == "switch":
            return i
        if stack[i].kind == "knot":
            return None
    return None


def _unclosed_brace_offsets(text: str) -> list[int]:
    """Return offsets of `{` chars that have no matching `}` in TEXT.

    Used to detect nested compact switches embedded in a marker's trailing text,
    e.g. `- {cycle:` or `- {condition:`. Returned offsets are in source order
    (outermost first).
    """
    stack: list[int] = []
    for i, c in enumerate(text):
        if c == "{":
            stack.append(i)
        elif c == "}":
            if stack:
                stack.pop()
    return stack


def _switch_has_branches_sequence(tokens: list[Token]) -> list[bool]:
    """Pre-pass: determine `has_branches` for each switch in push order.

    The comment-in-switch rule (rules.md §4.4) fires only for switches with
    explicit `-` branches. Since a comment can appear *before* the first branch
    in source order, we need to know up front whether each switch will have any
    branches. This walk mirrors the push/pop sequence in `indent_tokens` and
    returns one bool per switch frame, in push order.
    """
    result: list[bool] = []
    stack: list[int] = []  # indices into result for currently-open switches

    for tok in tokens:
        if tok.type is LineType.MARKER:
            # A `-` marker inside a switch is a branch of that switch.
            if tok.marker_char == "-" and stack:
                result[stack[-1]] = True
            # The marker's trailing text may open further nested switches.
            for _ in _unclosed_brace_offsets(tok.marker_rest):
                result.append(False)
                stack.append(len(result) - 1)
        elif tok.type in (LineType.BRACE_OPEN, LineType.COMPACT_SWITCH):
            result.append(False)
            stack.append(len(result) - 1)
        elif tok.type is LineType.BRACE_CLOSE:
            if stack:
                stack.pop()
        elif tok.type is LineType.KNOT or tok.type is LineType.STITCH:
            # Indent_tokens resets the stack on a knot/stitch boundary.
            stack.clear()

    return result


def _emit_marker_line(depth: int, char: str, rest: str, indent: int) -> str:
    """Render a marker line with normalized marker-token spacing."""
    marker_tokens = " ".join([char] * depth)
    if rest:
        return " " * indent + marker_tokens + " " + rest
    return " " * indent + marker_tokens


def indent_tokens(tokens: list[Token]) -> list[str]:
    """Walk TOKENS, emit each as a properly-indented line.

    Implements the natural-alignment rule from rules.md §1.
    """
    out: list[str] = []
    stack: list[Frame] = [Frame(kind="knot", base_col=0)]
    has_branches_seq = _switch_has_branches_sequence(tokens)
    switch_push_idx = 0

    def top() -> Frame:
        return stack[-1]

    def push_switch(base_col: int) -> None:
        nonlocal switch_push_idx
        has_branches = (
            has_branches_seq[switch_push_idx]
            if switch_push_idx < len(has_branches_seq)
            else False
        )
        switch_push_idx += 1
        stack.append(
            Frame(kind="switch", base_col=base_col, has_branches=has_branches)
        )

    for tok in tokens:
        if tok.type is LineType.BLANK:
            out.append("")
            continue

        if tok.type is LineType.KNOT or tok.type is LineType.STITCH:
            # Knot/stitch resets the indentation context to a fresh knot body.
            stack.clear()
            stack.append(Frame(kind="knot", base_col=0))
            out.append(tok.body)
            continue

        if tok.type is LineType.DECLARATION or tok.type is LineType.TODO:
            out.append(tok.body)
            continue

        if tok.type is LineType.BLOCK_COMMENT:
            # Preserve original indent for block comments — they're typically
            # section headers with intentional internal layout.
            out.append(" " * tok.indent + tok.body)
            continue

        if tok.type is LineType.MARKER:
            depth = tok.marker_depth
            char = tok.marker_char
            marker_len = 2 * depth - 1

            switch_idx = _find_enclosing_switch(stack)
            is_branch = switch_idx is not None and char == "-"
            is_gather = switch_idx is None and char == "-"

            if is_branch:
                # Switch branch: pop everything above the switch, place at brace_col.
                del stack[switch_idx + 1 :]
                switch_frame = stack[switch_idx]
                marker_col = switch_frame.base_col
            else:
                # Choice/gather: pop any markers at depth >= D so we can place a peer.
                while top().kind == "marker" and top().marker_depth >= depth:
                    stack.pop()
                marker_col = top().child_marker_col

            stack.append(
                Frame(
                    kind="marker",
                    base_col=marker_col,
                    marker_depth=depth,
                    marker_char=char,
                    marker_col=marker_col,
                    marker_len=marker_len,
                    is_gather=is_gather,
                )
            )
            out.append(_emit_marker_line(depth, char, tok.marker_rest, marker_col))
            # If the marker's trailing text opens a switch (e.g. `- {cycle:`),
            # push a switch frame so subsequent branches and the closing `}`
            # align with the inner `{`, not the outer scope.
            rest_start_col = marker_col + marker_len + 1
            for offset in _unclosed_brace_offsets(tok.marker_rest):
                push_switch(rest_start_col + offset)
            continue

        if tok.type in (
            LineType.CONTENT,
            LineType.CODE,
            LineType.DIVERT,
            LineType.LINE_COMMENT,
        ):
            # Source-indent dedent signal: if the line sits at or before the
            # current marker's column, the author has left that marker's scope.
            # Pop markers (not switches — those close on `}`) accordingly.
            while top().kind == "marker" and tok.indent <= top().marker_col:
                stack.pop()
            # rules.md §4.4: a line comment inside a switch with explicit `-`
            # branches aligns with those branch markers (= the opening `{`'s
            # column). In a branch-less switch (just unconditional content),
            # comments stay at the regular content column.
            if (
                tok.type is LineType.LINE_COMMENT
                and top().kind == "switch"
                and top().has_branches
            ):
                col = top().base_col
            else:
                col = top().content_col
            out.append(" " * col + tok.body)
            continue

        if tok.type is LineType.BRACE_OPEN or tok.type is LineType.COMPACT_SWITCH:
            while top().kind == "marker" and tok.indent <= top().marker_col:
                stack.pop()
            brace_col = top().content_col
            out.append(" " * brace_col + tok.body)
            push_switch(brace_col)
            continue

        if tok.type is LineType.BRACE_CLOSE:
            # Pop markers/branches above the switch, then pop the switch itself.
            switch_idx = _find_enclosing_switch(stack)
            if switch_idx is not None:
                brace_col = stack[switch_idx].base_col
                del stack[switch_idx:]
            else:
                brace_col = top().content_col
            out.append(" " * brace_col + tok.body)
            continue

        # Unknown — preserve original line.
        out.append(tok.raw)

    return out


# ---------- Verification harness (--verify-blocks) ----------

_RE_DEF_START = re.compile(r"^(=|=== )")


def scaffold_block(content: str) -> str:
    """Wrap a partial Ink snippet so inkjs-compiler can compile it.

    Inserts `-> END` before the first knot/stitch/function definition, so the
    entry-point content (anything that runs before any definition) has an
    explicit terminus. If the block has no definitions, `-> END` is appended.
    See SKILL.md "Partial snippets" for the rationale.
    """
    lines = content.split("\n")
    first_def_idx = len(lines)
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("===") or _RE_DEF_START.match(stripped):
            first_def_idx = i
            break
    if first_def_idx == len(lines):
        # No definitions — terminate the entry-point.
        tail = "" if content.rstrip().endswith("-> END") else "\n-> END\n"
        return content.rstrip("\n") + tail
    entry = "\n".join(lines[:first_def_idx])
    defs = "\n".join(lines[first_def_idx:])
    return entry.rstrip("\n") + "\n-> END\n" + defs


def _find_inkjs_compiler() -> str | None:
    """Locate inkjs-compiler via env var, PATH, or a common local install."""
    env = os.environ.get("INKJS_COMPILER")
    if env and Path(env).is_file():
        return env
    via_path = shutil.which("inkjs-compiler")
    if via_path:
        return via_path
    local = Path.cwd() / "node_modules" / ".bin" / "inkjs-compiler"
    if local.is_file():
        return str(local)
    return None


def _compile_to_json(content: str, work_dir: Path, name: str, compiler: str) -> tuple[bool, object, str]:
    """Compile CONTENT and return (ok, json_data, error_summary)."""
    ink_path = work_dir / f"{name}.ink"
    ink_path.write_text(content, encoding="utf-8")
    proc = subprocess.run(
        [compiler, str(ink_path)],
        capture_output=True,
        text=True,
    )
    # inkjs-compiler prints errors on both stdout and stderr depending on the case.
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    errors = [line for line in output.splitlines() if "ERROR:" in line]
    if errors:
        return False, None, errors[0]
    json_path = ink_path.with_suffix(".ink.json")
    if not json_path.exists():
        return False, None, "compile produced no JSON output"
    try:
        with open(json_path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        return False, None, f"json parse error: {e}"
    return True, data, ""


def _canonical_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, indent=2)


def verify_markdown_blocks(md_path: Path, compiler: str) -> int:
    """Compile every ```ink block, before and after formatting; JSON-diff each.

    Outcomes per block:
      PASS  — both compile, JSON identical
      FAIL  — both compile but JSON differs, or formatter breaks a compiling block
      WARN  — formatter "fixes" a compile error (surprising; investigate)
      SKIP  — both fail to compile (partial snippet with external references)

    Returns 0 if no FAIL/WARN, 1 otherwise.
    """
    text = md_path.read_text(encoding="utf-8")
    blocks = list(extract_ink_blocks(text))
    if not blocks:
        print(f"verify-blocks {md_path}: no ```ink blocks found")
        return 0

    n_pass = n_fail = n_skip = n_warn = 0
    failures: list[tuple[int, str, str]] = []

    with tempfile.TemporaryDirectory(prefix="ink-verify-") as tmp:
        tmp_dir = Path(tmp)
        for i, block in enumerate(blocks):
            orig_scaffolded = scaffold_block(block.content)
            formatted_content = format_ink(block.content)
            new_scaffolded = scaffold_block(formatted_content)

            orig_ok, orig_json, orig_err = _compile_to_json(
                orig_scaffolded, tmp_dir, f"block-{i}-orig", compiler
            )
            new_ok, new_json, new_err = _compile_to_json(
                new_scaffolded, tmp_dir, f"block-{i}-new", compiler
            )

            if not orig_ok and not new_ok:
                n_skip += 1
                continue
            if not orig_ok and new_ok:
                n_warn += 1
                failures.append((block.open_line, "WARN: formatter fixed compile error", orig_err))
                continue
            if orig_ok and not new_ok:
                n_fail += 1
                failures.append((block.open_line, "FAIL: formatter broke compile", new_err))
                continue
            if _canonical_json(orig_json) == _canonical_json(new_json):
                n_pass += 1
            else:
                n_fail += 1
                failures.append((block.open_line, "FAIL: JSON differs", ""))

    total = len(blocks)
    print(
        f"verify-blocks {md_path}: {total} blocks — "
        f"{n_pass} pass, {n_fail} fail, {n_skip} skip, {n_warn} warn"
    )
    for line_no, reason, detail in failures:
        suffix = f" — {detail}" if detail else ""
        print(f"  block @ line {line_no}: {reason}{suffix}")

    return 0 if (n_fail == 0 and n_warn == 0) else 1


def verify_ink_file(path: Path, compiler: str) -> int:
    """Compile a whole .ink file before and after formatting; JSON-diff."""
    text = path.read_text(encoding="utf-8")
    formatted = format_ink(text)
    with tempfile.TemporaryDirectory(prefix="ink-verify-") as tmp:
        tmp_dir = Path(tmp)
        orig_ok, orig_json, orig_err = _compile_to_json(text, tmp_dir, "orig", compiler)
        new_ok, new_json, new_err = _compile_to_json(formatted, tmp_dir, "new", compiler)
    if not orig_ok:
        print(f"verify {path}: original does not compile: {orig_err}", file=sys.stderr)
        return 2
    if not new_ok:
        print(f"verify {path}: FAIL — formatted does not compile: {new_err}", file=sys.stderr)
        return 1
    if _canonical_json(orig_json) == _canonical_json(new_json):
        print(f"verify {path}: PASS")
        return 0
    print(f"verify {path}: FAIL — JSON differs", file=sys.stderr)
    return 1


def format_ink(text: str) -> str:
    """Apply Ink style formatting to a single .ink source string.

    Runs the lexer, token normalizer, and indenter. Brace-expression handling
    (§4.1) and markdown wrapping come in subsequent commits.
    """
    tokens = lex(text)
    tokens = normalize_tokens(tokens)
    lines = indent_tokens(tokens)
    # Preserve trailing newline if the input had one.
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + trailing


@dataclass
class InkBlock:
    """One ```ink fenced block extracted from a markdown file."""

    open_line: int  # 1-based line number of the opening ```ink fence
    close_line: int  # 1-based line number of the closing ``` fence
    content: str  # block contents (between the fences), trailing newline included


def extract_ink_blocks(text: str) -> Iterator[InkBlock]:
    """Yield each ```ink fenced block in TEXT.

    Untagged ``` ``` and other-language fences are ignored. Unclosed fences
    at end-of-file are silently dropped.
    """
    lines = text.splitlines(keepends=True)
    in_block = False
    open_line = 0
    block_lines: list[str] = []
    for idx, line in enumerate(lines):
        stripped = line.rstrip("\n").rstrip("\r")
        if not in_block and stripped == "```ink":
            in_block = True
            open_line = idx + 1
            block_lines = []
            continue
        if in_block and stripped == "```":
            yield InkBlock(
                open_line=open_line,
                close_line=idx + 1,
                content="".join(block_lines),
            )
            in_block = False
            block_lines = []
            continue
        if in_block:
            block_lines.append(line)


def format_markdown(text: str) -> str:
    """Format only the ```ink fenced blocks inside a markdown file.

    The surrounding prose, untagged ``` ``` blocks, and blocks tagged for
    other languages are left untouched. Only fences whose info string is
    exactly `ink` are formatted.
    """
    lines = text.splitlines(keepends=True)
    blocks = list(extract_ink_blocks(text))
    # Build a map from block-content-start-line (0-based) to formatted content.
    # Substitute each block's content lines in place; copy everything else verbatim.
    block_by_open: dict[int, InkBlock] = {b.open_line: b for b in blocks}
    out: list[str] = []
    idx = 0
    while idx < len(lines):
        line_no = idx + 1
        if line_no in block_by_open:
            block = block_by_open[line_no]
            out.append(lines[idx])  # the ```ink opener
            out.append(format_ink(block.content))
            # Skip block content lines; emit the closer.
            close_idx = block.close_line - 1
            out.append(lines[close_idx])
            idx = close_idx + 1
            continue
        out.append(lines[idx])
        idx += 1
    return "".join(out)


def format_file(path: Path) -> tuple[str, str]:
    """Read PATH and return (original, formatted)."""
    original = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        formatted = format_markdown(original)
    else:
        formatted = format_ink(original)
    return original, formatted


def print_diff(original: str, formatted: str, path: Path) -> None:
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        formatted.splitlines(keepends=True),
        fromfile=str(path),
        tofile=f"{path} (formatted)",
    )
    sys.stdout.writelines(diff)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply Ink style formatting to a .ink or .md file.",
    )
    parser.add_argument("file", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Print diff to stdout; exit 1 if changes needed. Do not write.",
    )
    mode.add_argument(
        "--stdout",
        action="store_true",
        help="Print formatted output to stdout. Do not write.",
    )
    mode.add_argument(
        "--debug-tokens",
        action="store_true",
        help="Print the lexer's token classification, one line per source line. Diagnostic.",
    )
    mode.add_argument(
        "--verify-blocks",
        action="store_true",
        help=(
            "Compile each ink block (or whole .ink file) before and after formatting; "
            "compare JSON. Exits 1 if any block fails. Requires inkjs-compiler "
            "(searched via $INKJS_COMPILER, PATH, ./node_modules/.bin)."
        ),
    )
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2

    if args.debug_tokens:
        source = args.file.read_text(encoding="utf-8")
        for i, tok in enumerate(lex(source), start=1):
            extra = ""
            if tok.type is LineType.MARKER:
                extra = f" depth={tok.marker_depth} char={tok.marker_char!r}"
            print(f"{i:4d}  {tok.type.value:14s} indent={tok.indent:<3d}{extra}  {tok.body!r}")
        return 0

    if args.verify_blocks:
        compiler = _find_inkjs_compiler()
        if not compiler:
            print(
                "error: inkjs-compiler not found. Set $INKJS_COMPILER or install via npm.",
                file=sys.stderr,
            )
            return 2
        if args.file.suffix == ".md":
            return verify_markdown_blocks(args.file, compiler)
        return verify_ink_file(args.file, compiler)

    original, formatted = format_file(args.file)

    if args.stdout:
        sys.stdout.write(formatted)
        return 0

    if args.check:
        if original == formatted:
            return 0
        print_diff(original, formatted, args.file)
        return 1

    if original != formatted:
        args.file.write_text(formatted, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
