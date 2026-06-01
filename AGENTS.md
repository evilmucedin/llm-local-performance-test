# Coding-agent guide

This file is for coding agents and agentic IDEs such as Pi, Claude Code, and similar tools. It documents how to work safely in this repository.

## Project summary

`llm-local-performance-test` is a Python package and CLI for estimating local LLM throughput. It has a simple hardware-only mode and a fuller mode that can also benchmark a local Ollama model.

Read `ARCHITECTURE.md` before changing estimation logic, output fields, or Ollama behavior.

## Common commands

```bash
# Fast validation path
python run.py --simple

# Full path without waiting for a real Ollama server
OLLAMA_HOST=http://127.0.0.1:9 python run.py

# Syntax/import validation
python -m compileall src run.py

# Installed-entry-point style, after pip install -e .
llm-local-perf --simple
llm-local-perf
cursor-ollama --no-launch
```

The project currently has no dedicated unit-test suite. Prefer adding tests when introducing behavior that can be tested without real hardware or Ollama.

## Development conventions

- Keep runtime dependencies minimal. Do not add a dependency unless the value is clear and documented.
- Keep `--simple` fast, offline, and robust.
- Full mode may contact Ollama, but must still succeed when Ollama is unavailable.
- Preserve human-readable output; this is a CLI-first project.
- When adding a value to the detailed output, consider whether it also belongs in the full-mode quick view.
- Use small, platform-tolerant probes. Missing tools like `nvidia-smi` must not crash the CLI.
- Use standard-library APIs where possible.

## Pricing changes

Claude-equivalent cost math lives in `src/llm_local_perf/pricing.py`.

If updating pricing:

1. Update the constant and naming in `pricing.py`.
2. Keep generated-token estimates compared to output-token pricing unless the estimation model changes.
3. Update `ARCHITECTURE.md` and `README.md` if the user-visible interpretation changes.
4. Include the rate and source in the PR description.

## Ollama changes

For benchmark consistency, keep fixed generation options unless there is a strong reason to change them:

- `OLLAMA_NUM_CTX = 512`
- `OLLAMA_NUM_PREDICT = 100`
- `temperature = 0.0`

If these change, update `ARCHITECTURE.md` and explain how comparability is affected.

## Pull request checklist

Before opening a PR, run at least:

```bash
python run.py --simple
OLLAMA_HOST=http://127.0.0.1:9 python run.py
python -m compileall src run.py
```

In the PR body, include:

- Summary of user-visible output changes.
- Validation commands and results.
- Any pricing assumptions or benchmark-setting changes.
- Whether a real Ollama benchmark was run.

## Advice for Claude Code

- Start by reading `README.md`, `ARCHITECTURE.md`, and this file.
- Prefer focused diffs and short explanations.
- Use `python run.py --simple` for quick feedback before trying full mode.
- Do not assume the machine has NVIDIA GPU support or a reachable Ollama server.
- If adding project memory for Claude, keep `CLAUDE.md` short and point back to this canonical guide to avoid duplicated stale instructions.

## Advice for Pi

- Pi loads context files such as `AGENTS.md` / `CLAUDE.md`; this file is intended to be safe startup context.
- Use `@README.md` or `@ARCHITECTURE.md` in prompts when asking Pi for targeted changes.
- In interactive Pi sessions, use `/session` to inspect token/cost usage and `/compact` when the context gets large.
- For low-risk review prompts, run Pi with read-only tools, for example:

```bash
pi --tools read,grep,find,ls -p "Review this repository for documentation gaps"
```

- For implementation work, let Pi use file-editing tools but ask it to run the validation commands above before summarizing.
- If using Pi packages, skills, or extensions, review their source first because they can execute code with local permissions.
