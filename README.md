# cloud-cli

White-labeled frontend for a self-hosted reasoning endpoint, built on top of
[aider-chat](https://aider.chat). Patches aider's IO, prompts, and message
routing at import time so the terminal UI is sleek, the system prompt is
tight, and every user message is automatically routed through a 51-skill
registry.

## Why this exists

The upstream aider terminal UI assumes an Anthropic/OpenAI-shaped local
client. This wrapper is for environments where the model is a 70B-class
reasoning endpoint served behind an OpenAI-compatible base URL. The wrapper
fixes three recurring failure modes of the upstream on that model:

1. `npx live` / phantom `package.json` / invented dev servers for static
   HTML/CSS/JS sites. **Fixed by the `Static Site, No Build Step` skill.**
2. URL auto-detection that triggers aider's Playwright installer as soon as a
   CDN script is mentioned. **Fixed by always passing `--disable-playwright`
   and `--no-detect-urls`.**
3. Chat mode leaking into build mode across turns (the model summarises
   instead of writing files, then the next turn inherits the read-only
   prompts). **Fixed in the interactive loop by resetting `gpt_prompts` from
   a fresh baseline on every turn.**

## Quick start

```bash
git clone https://github.com/<your-org>/cloud-cli.git
cd cloud-cli

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure the endpoint your wrapper should talk to:
cat > ~/.aider.env <<'EOF'
export OPENAI_API_BASE=https://your-endpoint.example/v1
export OPENAI_API_KEY=sk-...
EOF
export OPENAI_API_BASE OPENAI_API_KEY      # optional; the launcher reads ~/.aider.env anyway

python3 cloud_cli_launcher.py
```

That's it — no `setup.py`, no build step, no global install. The launcher is
just two Python files.

## Flags

```
python3 cloud_cli_launcher.py                 # interactive, default behaviour
python3 cloud_cli_launcher.py --explain       # force read-only Q&A for the whole session
python3 cloud_cli_launcher.py --no-clarify    # never ask clarifying questions; always build
python3 cloud_cli_launcher.py --message "..." --exit    # one-shot
```

`--fast` is deliberately rejected: the 70B reasoning model mangles
unified-diff SEARCH/REPLACE blocks, so whole-file is the only reliable edit
format on this endpoint.

The launcher also forces these upstream flags regardless of argv:
`--disable-playwright` and `--no-detect-urls`.

## How it works

`cloud_cli_launcher.py` makes six additions on top of upstream aider:

1. Loads `~/.aider.env` so `OPENAI_API_BASE` / `OPENAI_API_KEY` are present
   even when `~/.zshrc` has not been sourced.
2. Replaces the startup banner, model/repo banner, prompt marker, divider,
   and few-shot examples with a branded UI.
3. Auto-routes every user message through the 51-skill registry
   (`skills_registry.py`) and injects matched skills into the system context.
4. Detects short, broad "build me X" requests and tells the model to ask
   2-3 clarifying questions before writing files. Disabled with `--no-clarify`.
5. Switches the model's system prompt per turn: chat turns use read-only Q&A
   prompts so the model cannot invent files; build turns restore the
   file-writing coder.
6. Auto-adds real workspace files to the chat on build turns so the model
   edits what exists instead of inventing filenames.

All six are layered onto upstream aider with monkey-patching — no fork of
aider-chat needed, so you can `pip install -U aider-chat` to upgrade.

## Skills

51 concise engineering "skills" across 5 domains (UI/UX, Frontend, Backend,
System Design, DevOps). Each carries a name, trigger keywords, and a
directive that gets injected into the system prompt when matched.

A new skill call has a small surface area:

```python
_s("Skill Name", DOMAINS[1],
   ["trigger", "keywords"],
   "The directive text injected into the system prompt."),
```

Add it to the appropriate `<DOMAIN>` list and the registry's own assertion
will tell you if you've gone over 51.

## Files in this repo

```
cloud_cli_launcher.py   # the wrapper. ~770 lines.
skills_registry.py      # 51 skills + match_scoring + stack detection.
requirements.txt        # pins aider-chat[playwright]==0.86.2
.gitignore
```

You will see `aider-workspace/` materialise locally as `.venv/` when you
install — that's expected and is the upstream package's sandbox.

## License

MIT.
