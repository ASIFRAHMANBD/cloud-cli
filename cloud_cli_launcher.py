#!/usr/bin/env python3
"""
Cloud CLI - a white-labeled front end for a self-hosted reasoning endpoint.

Adds four things on top of the upstream coding agent:
  1. Loads ~/.aider.env automatically so OPENAI_API_BASE / OPENAI_API_KEY are
     present even when ~/.zshrc has not been sourced.
  2. Replaces the upstream's startup banner, model/repo banner lines, prompt
     marker, horizontal rule, and few-shot examples with a sleek, branded UI.
  3. Auto-routes every user message through the 50-skill registry in
     `skills_registry.py` and injects matched skills into the system context.
  4. Detects short, broad "build me X" requests and tells the model to ask
     2-3 clarifying questions before writing files.
  5. Switches the model's system prompt PER TURN: clarification/chat turns run
     in read-only Q&A mode (the model cannot invent files), while build turns
     restore the file-writing coder.
  6. Auto-adds real workspace files to the chat on build turns so the model
     edits files that actually exist instead of inventing filenames.

  cloud-cli                      # interactive, auto switch per turn
  cloud-cli --explain            # force read-only Q&A for the whole session
  cloud-cli --no-clarify         # never ask clarifying questions; always build
  cloud-cli --message "..." --exit

  NOTE: there is deliberately no --fast / diff-fenced mode. The 70B
  reasoning model mangles unified-diff SEARCH/REPLACE blocks, so whole-file
  is the only reliable edit format on this endpoint.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Optional

ENV_FILE = Path.home() / ".aider.env"
SUPERPOWERS_FILE = Path.home() / ".cloud-cli" / "skills" / "core_superpowers.md"

# Lazily populated cache for the Core Superpowers markdown.
_SUPERPOWERS_CACHE: Optional[str] = None


def load_superpowers(path: Path = SUPERPOWERS_FILE) -> str:
    """
    Read the Core Superpowers markdown doc. Cached after the first read so we
    don't hit disk on every turn. Missing or unreadable files return an empty
    string - the laws in `short_system` remain in effect even without the doc.
    """
    global _SUPERPOWERS_CACHE
    if _SUPERPOWERS_CACHE is not None:
        return _SUPERPOWERS_CACHE
    text = ""
    try:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    _SUPERPOWERS_CACHE = text
    return text

LAUNCHER_DIR = Path(__file__).resolve().parent
if str(LAUNCHER_DIR) not in sys.path:
    sys.path.insert(0, str(LAUNCHER_DIR))

import skills_registry as skills  # noqa: E402  (after sys.path tweak)

ACCENT = "#38bdf8"
PROMPT_MARKER = "cloud-cli ❯ "

# Prefixes the upstream prints at startup that we want to silence.
_NOISE_PREFIXES = (
    "aider v",
    "aider version",
    "main model:",
    "model:",
    "weak model:",
    "editor model:",
    "git repo:",
    "repo-map:",
    "warning:",
    "added ",
    "see:",
)

# --------------------------------------------------------------------------
# Substrings injected by aider's reasoning_tags module that we strip so the
# terminal output matches a clean modern UI.
# --------------------------------------------------------------------------
_ANSWER_DIVIDERS = (
    "► **THINKING**",
    "► **ANSWER**",
    "► THINKING",
    "► ANSWER",
)


# --------------------------------------------------------------------------
# 1. Credential bootstrap (~/.aider.env)
# --------------------------------------------------------------------------


def load_env(path: Path = ENV_FILE) -> None:
    """
    Parse ~/.aider.env into os.environ without clobbering values already set.

    Supports plain `KEY=value` and shell-style `export KEY=value` lines; values
    may be optionally surrounded by single or double quotes.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and val:
            os.environ.setdefault(key, val)


# --------------------------------------------------------------------------
# 2. Banner
# --------------------------------------------------------------------------


def _workspace_label() -> str:
    """
    Best-effort name of the current workspace. Never raises: if the cwd has
    been deleted underneath us (common after a `rm -rf` on a scratch dir),
    fall back to a safe placeholder instead of crashing the launcher.
    """
    try:
        cwd = os.getcwd()
    except OSError:
        return "(unavailable)"
    return os.path.basename(cwd) or cwd


def print_banner() -> None:
    from rich.console import Console
    from rich.panel import Panel

    console = Console(width=100)
    workspace = _workspace_label()
    header = (
        f"[bold]⚡ Cloud CLI[/]  [dim]•[/]  Self-Customized Model (70M+ Dataset)"
        f"  [dim]•[/]  Workspace: [bold]{workspace}[/]"
    )
    hint = (
        "Engine: Active  [dim]•[/]  "
        "Commands: /add <file>  •  /run <cmd>  •  /undo  •  /clear  •  exit"
    )
    console.print(
        Panel(
            f"{header}\n[dim]{hint}[/]",
            title=None,
            border_style=ACCENT,
            padding=(0, 2),
        )
    )


# --------------------------------------------------------------------------
# 3. IO patch: silence boilerplate, drop horizontal rule, restyle prompt
# --------------------------------------------------------------------------


def _retitle_prompt(fn):
    """
    Rebuild the upstream get_input with its trailing '> ' prompt marker
    replaced by our brand, without vendoring the whole method body.
    """
    src = textwrap.dedent(inspect.getsource(fn))
    patched = src.replace('prompt_prefix += "> "', f"prompt_prefix += {PROMPT_MARKER!r}")
    if patched == src:
        raise RuntimeError("cloud-cli: could not locate the prompt marker to restyle")

    module = type(sys)("cloud_cli_prompt")
    module.__dict__.update(
        {k: v for k, v in fn.__globals__.items() if not k.startswith("__")}
    )
    exec(compile(patched, "<cloud-cli-prompt>", "exec"), module.__dict__)
    return module.__dict__["get_input"]


def _sanitize_malformed_fence_headers(text: str) -> str:
    """
    The 70B occasionally emits a stray filename line that is actually a code
    fragment, e.g. `updateDisplay();` or `});` immediately followed by a code
    fence. aider interprets that bare line as the filename and writes a 0-byte
    file. Strip any line that (a) has no extension OR (b) ends with a code
    punctuation character when it appears immediately before a fenced block.

    The rule is conservative: we only redact suspicious lines that are also
    immediately followed by a `\\`\\`\\`\\`` fence. Real filenames always have
    a `.` and at least one alphanumeric character in their extension, and they
    are not followed by an opening fence unless the previous line is the body.
    """
    lines = text.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        is_opening_fence = next_line.startswith("```") and not next_line == "```"
        is_likely_real_filename = (
            "." in stripped
            and not any(stripped.endswith(c) for c in (";", "{", "}", "(", ")", "[", "]"))
            and len(stripped.split(".")[-1]) >= 1
            and stripped.split(".")[-1].isalnum()
            and " " not in stripped
        )
        if is_opening_fence and not is_likely_real_filename:
            # Drop the malformed header so aider never creates a junk file.
            out.append(f"# [cloud-cli: dropped malformed filename `{stripped}`]")
            continue
        out.append(line)
    return "\n".join(out)


def patch_io() -> None:
    """Silence upstream boilerplate, drop the divider rule, restyle the prompt."""
    from aider import io as aider_io

    original_tool_output = aider_io.InputOutput.tool_output
    original_assistant_output = aider_io.InputOutput.assistant_output

    def tool_output(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, str) and arg.strip().lower().startswith(_NOISE_PREFIXES):
                return
        return original_tool_output(self, *args, **kwargs)

    def assistant_output(self, message, pretty=None):
        if isinstance(message, str):
            cleaned = message
            for divider in _ANSWER_DIVIDERS:
                cleaned = cleaned.replace(divider, "")
            # Strip the leading/trailing artifact lines that were dividers.
            lines = cleaned.splitlines()
            cleaned = "\n".join(line for line in lines if line.strip())
            cleaned = cleaned.strip("\n")
            # Drop malformed filename lines that would create 0-byte junk files.
            cleaned = _sanitize_malformed_fence_headers(cleaned)
            if cleaned != message:
                return original_assistant_output(self, cleaned, pretty=pretty)
        return original_assistant_output(self, message, pretty=pretty)

    # Replace the horizontal rule divider with a soft blank line, keep input area quiet.
    def rule(self):
        # Print nothing on purpose: keeps the input area clean between turns.
        return

    aider_io.InputOutput.tool_output = tool_output
    aider_io.InputOutput.assistant_output = assistant_output
    aider_io.InputOutput.rule = rule
    aider_io.InputOutput.get_input = _retitle_prompt(aider_io.InputOutput.get_input)


# --------------------------------------------------------------------------
# 4. Few-shot prompt: drain the show_greeting.py example the 70B echoes
# --------------------------------------------------------------------------


_NEUTRAL_EXAMPLE = []


def patch_few_shot() -> None:
    """
    The upstream `WholeFilePrompts` injects a multi-shot example about
    `show_greeting.py` ("Change the greeting to be more casual"). On short
    user prompts the 70B then echoes that hallucinated task back. Swap it for
    a neutral one-liner so the model answers the actual request instead.
    """
    from aider.coders import (
        wholefile_prompts,
        editblock_prompts,
        editblock_fenced_prompts,
        patch_prompts,
        udiff_prompts,
    )

    targets = [
        wholefile_prompts.WholeFilePrompts,
        editblock_prompts.EditBlockPrompts,
        editblock_fenced_prompts.EditBlockFencedPrompts,
        patch_prompts.PatchPrompts,
        udiff_prompts.UnifiedDiffPrompts,
    ]
    for cls in targets:
        cls.example_messages = _NEUTRAL_EXAMPLE

    # Shorten the verbose multi-step main_system that primes long narration,
    # and install the four absolute laws this model must obey every turn.
    short_system = (
        "You are an expert coding assistant. Answer the user's most recent "
        "request briefly and only that request, then produce the requested "
        "files. Do not list steps or restate the task.\n\n"
        "Strict laws you MUST follow in every response:\n"
        "\n"
        "LAW 1 (NO FAKE PATHS): NEVER use placeholder paths such as "
        "`path/to/file` or `src/file`. Write files directly to the current "
        "working directory using just the filename, e.g. `index.html` or "
        "`main.js`. Do not invent folder structures the user did not request.\n"
        "\n"
        "LAW 2 (STRICT FILE FORMAT): To create or modify a file you MUST "
        "emit exactly this layout, with no extra commentary or markup:\n"
        "\n"
        "filename.ext\n"
        "```language\n"
        "entire file content here\n"
        "```\n"
        "\n"
        "The first line is the exact filename. The second line is opening "
        "triple backticks with a language tag. The body is the entire file "
        "contents. The closing line is exactly three backticks on their own.\n"
        "\n"
        "LAW 2 HARD RULES (violating these corrupts the user's filesystem):\n"
        "  a) NEVER split a single file across multiple fenced blocks.\n"
        "  b) NEVER emit a filename that is a fragment of code such as "
        "`updateDisplay();` or `console.log('x')`. A filename is ONLY "
        "a bare name with a real extension like `index.html` or `app.js`.\n"
        "  c) ALWAYS close every code fence. If you run out of tokens, close "
        "the fence first, then stop.\n"
        "  d) When in doubt, emit FEWER files, each complete.\n"
        "\n"
        "LAW 3 (EXECUTION VIA /run): You cannot install packages or start "
        "servers yourself. When the user needs `npm install`, `pip install`, "
        "`npm run dev`, `python main.py`, `docker compose up`, or any other "
        "shell action, output the exact command for the user to run, in the "
        "form `/run <full command>` (e.g. `/run npm install`, "
        "`/run python main.py`). Use `/run` once per command, on its own "
        "line. Do not invent an execution result; cloud-cli reports what was "
        "actually run.\n"
        "\n"
        "LAW 4 (NO NARRATION): Do not enumerate steps. Do not say you are "
        "about to do something. Produce the file(s) directly after at most a "
        "one-line statement of intent."
    )

    # Append the user-authored Core Superpowers laws from
    # ~/.cloud-cli/skills/core_superpowers.md. This is read once per process
    # and cached, so editing that file takes effect on the next launch.
    superpowers = load_superpowers()
    if superpowers:
        short_system = (
            f"{short_system}\n\n"
            "Additional binding rules (Core Superpowers), which override any "
            "conflicting instruction:\n\n"
            f"{superpowers}"
        )

    for cls in targets:
        if hasattr(cls, "main_system"):
            # Brace-escape so any literal `}` in our text or in a user's
            # superpowers doc cannot break aider's str.format() pass later.
            cls.main_system = _brace_escape(short_system)


# --------------------------------------------------------------------------
# 5. Skill injection + clarification: intercept every user message
# --------------------------------------------------------------------------


_INTERCEPTED_MESSAGES: list[str] = []  # for tests / future telemetry


def _format_matched_block(matched) -> str:
    return skills.build_directive_block(matched)


def _maybe_clarify(prompt: str, matched) -> tuple[str, bool]:
    """
    For short, broad "build me X" requests, append a clarifying instruction
    so the model asks 2-3 short questions instead of writing files immediately.
    """
    if not skills.wants_clarification(prompt):
        return prompt, False

    skill_block = _format_matched_block(matched)
    if skill_block:
        skill_block = "\n\n" + skill_block
    decorated = (
        f"{prompt.rstrip()}{skill_block}\n\n"
        "Before writing any files, briefly ask 2-3 short clarifying questions: "
        "(1) preferred stack, (2) the 2-3 features that matter most, "
        "(3) visual style or design direction, with a recommended default for each. "
        "Then tell the user exactly: "
        "'Reply with your choices, or type `go` to build immediately with my recommended stack.'"
    )
    return decorated, True


def _maybe_build_directive(prompt: str, matched) -> str:
    skill_block = _format_matched_block(matched)
    if not skill_block:
        return prompt
    return f"{prompt.rstrip()}\n\n{skill_block}\n\n{skills.BUILD_INSTRUCTION}"


def _brace_escape(text: str) -> str:
    """
    Double every ``{`` and ``}`` so the result is safe to feed through
    ``str.format(**mapping)`` even when the original contains literal code
    samples (e.g. ``});``). This protects against `ValueError: Single '}'
    encountered in format string`, which crashes the whole launcher when a
    skill's directive or the superpowers doc happens to include a brace.
    """
    return text.replace("{", "{{").replace("}", "}}")


def _safe_cwd() -> str:
    """os.getcwd() that degrades to / instead of raising on a deleted cwd."""
    try:
        return os.getcwd()
    except OSError:
        return "/"


def _skill_status_line(prompt: str) -> str:
    matched = skills.match_skills(prompt, root=_safe_cwd(), limit=8)
    return skills.format_activation_line(matched), matched


def _print_with_style(line: str, color: str) -> None:
    """Emit a single styled line to stderr (does not pollute stdout)."""
    try:
        from rich.console import Console
        Console().print(line, style=color, highlight=False)
    except Exception:
        print(line)


def patch_message_interception(explain_only: bool = False, skip_clarify: bool = False) -> None:
    """
    Wrap `Coder.run` so every user message (from --message, --message-file, or
    the interactive prompt) is:
      * matched against the 50-skill registry
      * run in read-only Q&A mode when it is a clarification/chat turn, so the
        model can never invent a file on an open-ended prompt
      * run in whole-file write mode when it is a build/edit turn, with real
        workspace files auto-added to the chat so it edits what actually exists

    `skip_clarify=True` disables the clarification pre-probe entirely, so every
    prompt goes straight to file-writing mode.
    """
    from aider.coders.base_coder import Coder
    from aider.coders.ask_prompts import AskPrompts

    original_run = Coder.run
    read_only_prompts = AskPrompts()

    def _run_one(coder, message, preproc):
        decorated, ask_only, matched = _decorate_message(message, skip_clarify=skip_clarify)
        _INTERCEPTED_MESSAGES.append(message)
        _print_with_style(skills.format_activation_line(matched), color=ACCENT)

        read_only = explain_only or ask_only

        # Stash the mode so the prompt swap happens in get_input for the
        # interactive path, and here for the --message one-shot path.
        coder.io._cloud_read_only = read_only

        if not read_only:
            _autofill_files(coder, message)
            _print_with_style(
                "🔧 Build mode — writing real files", color="#34d399",
            )
        else:
            coder.gpt_prompts = read_only_prompts
            _print_with_style(
                "💬 Chat mode — read-only, no files will be written",
                color="#fbbf24",
            )

        return coder.run_one(decorated, preproc)

    def run_with_skill_routing(self, with_message=None, preproc=True):
        if with_message:
            # One-shot: run exactly one turn through our decorator.
            result = _run_one(self, with_message, preproc)
            return result

        # Interactive loop: route every typed line through the decorator.
        original_get_input = self.io.get_input
        # The coder's own prompts, captured once. Every turn restores from this
        # baseline so a read-only turn can never leak into the next build turn.
        write_prompts = self.gpt_prompts

        def sk_get_input(*args, **kwargs):
            user_msg = original_get_input(*args, **kwargs)
            if not user_msg:
                return user_msg

            # Always reset to write mode first, then downgrade if this turn
            # needs read-only. Never carry the previous turn's mode over.
            self.gpt_prompts = write_prompts
            decorated, ask_only, matched = _decorate_message(
                user_msg, skip_clarify=skip_clarify,
            )
            read_only = explain_only or ask_only

            if read_only:
                self.gpt_prompts = read_only_prompts
            else:
                _autofill_files(self, user_msg)

            _print_with_style(skills.format_activation_line(matched), color=ACCENT)
            _print_with_style(
                ("💬 Chat mode — read-only, no files will be written"
                 if read_only else "🔧 Build mode — writing real files"),
                color="#fbbf24" if read_only else "#34d399",
            )
            return decorated

        self.io.get_input = sk_get_input
        try:
            return original_run(self, with_message=None, preproc=preproc)
        finally:
            self.io.get_input = original_get_input
            self.gpt_prompts = write_prompts

    Coder.run = run_with_skill_routing


def _decorate_message(prompt: str, skip_clarify: bool = False) -> tuple[str, bool, list]:
    """
    Returns (decorated_message, asked_clarify, matched_skills).

    `asked_clarify` is True when the launcher should run this turn in
    read-only Q&A mode. When `skip_clarify` is True (e.g. `--no-clarify`), the
    clarification pre-probe is disabled and every prompt goes straight to the
    build directive.
    """
    matched = skills.match_skills(prompt, root=_safe_cwd(), limit=8)
    if not skip_clarify and skills.wants_clarification(prompt):
        return _maybe_clarify(prompt, matched)[0], True, matched
    return _maybe_build_directive(prompt, matched), False, matched


# --------------------------------------------------------------------------
# Workspace file injection: avoid invented filenames on build turns
# --------------------------------------------------------------------------


_SKIP_DIRS = (
    "node_modules", ".venv", "venv", ".git", "__pycache__", "dist", "build",
    ".next", ".nuxt", "site-packages", ".cache",
)

_DEFAULT_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".scss",
    ".go", ".rs", ".java", ".php", ".rb", ".json", ".yml", ".yaml",
    ".md", ".sql", ".sh",
}


def _discover_workspace_files(root: str, limit: int = 5) -> list[str]:
    """
    Return up to `limit` source files in the project root or its `src/`
    subfolder, ignoring common skip-dirs and oversized files.
    """
    candidates: list[str] = []
    roots = [root]
    src = os.path.join(root, "src")
    if os.path.isdir(src):
        roots.append(src)

    seen: set[str] = set()
    for base in roots:
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for name in entries:
            if name in _SKIP_DIRS or name.startswith("."):
                continue
            full = os.path.join(base, name)
            if full in seen or not os.path.isfile(full):
                continue
            seen.add(full)
            ext = os.path.splitext(name)[1].lower()
            if ext not in _DEFAULT_EXTS:
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            # Bulletproof rule: opportunistic auto-add only ever picks up files
            # under 8 KB. Larger files must be named explicitly by the user (via
            # /add or mentioned in the prompt) so a huge source file can never
            # silently consume the context window.
            if size > _AUTO_ADD_MAX_BYTES:
                continue
            candidates.append(full)
            if len(candidates) >= limit:
                return candidates
    return candidates


# Hard ceilings for the opportunistic (non-user-requested) file injection.
# _AUTO_ADD_MAX_BYTES : no single auto-added file may exceed 8 KB.
# _AUTO_ADD_MAX_TOKENS: the total auto-added set may not exceed 8k tokens.
# User-named files bypass _AUTO_ADD_MAX_BYTES but still respect the token cap,
# so an explicit request for a big file is honoured without letting the
# launcher itself blow the window.
_AUTO_ADD_MAX_BYTES = 8 * 1024
_AUTO_ADD_MAX_TOKENS = 8_000
_CONTEXT_BUDGET_TOKENS = _AUTO_ADD_MAX_TOKENS


def _mentioned_existing_files(prompt: str, root: str) -> list[str]:
    """
    Detect files that the user named in the prompt which actually exist on
    disk; return up to 5 absolute paths.
    """
    tokens = re.findall(r"[A-Za-z0-9_./-]+\.[A-Za-z0-9_-]{1,5}", prompt)
    found: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        rel = tok.strip("`'\"")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        full = os.path.join(root, rel)
        if os.path.isfile(full):
            found.append(full)
            if len(found) >= 5:
                break
    return found


def _autofill_files(coder, prompt: str) -> None:
    """
    If the chat has no files yet, add real workspace files (or files the
    user named that exist) so the model edits reality, not invented paths.

    BULLETPROOF BUDGET (LAW 4 of the bulletproof contract):

      * No single file auto-added without the user naming it may exceed
        `_AUTO_ADD_MAX_BYTES` (8 KB) — large files must be requested.
      * The cumulative auto-added file set may not exceed
        `_AUTO_ADD_MAX_TOKENS` (8k tokens), so we always leave at least
        8k of context for the model's own reasoning and output.

    A user naming a file in the prompt bypasses the per-file byte cap so a
    genuinely large file can still be edited when explicitly requested.
    """
    try:
        if getattr(coder, "abs_fnames", None):
            return

        root = getattr(coder, "root", None) or os.getcwd()
        targets = _mentioned_existing_files(prompt, root)

        # User-named files win and bypass the per-file byte cap.
        named = list(targets)

        # Everything else is opportunistic, so apply the 8 KB per-file cap.
        if not named:
            discover = _discover_workspace_files(root, limit=3)
        else:
            discover = []

        # User-named paths go in first and are not capped individually;
        # they are still capped by the global token budget below.
        ordered = named + discover
        byte_budget = _AUTO_ADD_MAX_TOKENS * 3  # ~3 bytes/token
        added_bytes = 0
        added_count = 0
        for full in ordered:
            try:
                rel = os.path.relpath(full, root)
            except ValueError:
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            # Skip files the user did not name if they exceed the per-file cap.
            if full not in named and size > _AUTO_ADD_MAX_BYTES:
                continue
            if added_bytes + size > byte_budget:
                break
            # Stop adding once we are clearly going to crowd out the model.
            if added_count >= 3:
                break
            coder.add_rel_fname(rel)
            added_bytes += size
            added_count += 1
    except Exception:
        # Never let convenience injection break the turn.
        pass


# --------------------------------------------------------------------------
# 6. CLI flags
# --------------------------------------------------------------------------


def build_argv(argv: list[str]) -> tuple[list[str], bool, bool]:
    """
    Translate cloud-cli flags into the upstream agent's flags.

    Returns (argv, explain_only, skip_clarify).

    There is deliberately no --fast: the 70B reasoning model cannot emit valid
    unified-diff SEARCH/REPLACE blocks, so diff-fenced is not offered.

    --explain pins the whole session to read-only Q&A mode.
    --no-clarify disables the "ask 2-3 questions first" pre-build probe so
       short broad prompts ('build me X') go straight to file writing.
    """
    out = []
    explain_only = False
    skip_clarify = False
    for arg in argv:
        if arg == "--explain":
            explain_only = True
        elif arg == "--no-clarify":
            skip_clarify = True
        elif arg == "--fast":
            raise SystemExit(
                "cloud-cli: --fast is no longer supported. This model cannot emit\n"
                "  reliable unified-diff blocks, so 'whole' is the only edit format.\n"
                "  Use the default build mode, or --explain for read-only Q&A."
            )
        else:
            out.append(arg)
    # Disable upstream URL scraping: the model sometimes references CDN scripts
    # (Tailwind, fonts) that trigger aider's auto-install of Playwright. We
    # never want that to happen in a build session.
    out += ["--disable-playwright", "--no-detect-urls"]
    return out, explain_only, skip_clarify


# --------------------------------------------------------------------------
# 7. Entry point
# --------------------------------------------------------------------------


def main() -> int:
    load_env()

    if not os.environ.get("OPENAI_API_BASE"):
        print(
            "error: OPENAI_API_BASE not set and not found in ~/.aider.env",
            file=sys.stderr,
        )
        return 1

    argv, explain_only, skip_clarify = build_argv(sys.argv[1:])

    patch_io()
    patch_few_shot()
    patch_message_interception(
        explain_only=explain_only, skip_clarify=skip_clarify,
    )
    print_banner()

    if explain_only:
        _print_with_style(
            "💬 --explain: read-only Q&A mode for this session", color="#fbbf24",
        )
    if skip_clarify:
        _print_with_style(
            "🛠 --no-clarify: every prompt goes straight to file writing",
            color="#34d399",
        )

    from aider.main import main as agent_main

    return agent_main(argv=argv)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)