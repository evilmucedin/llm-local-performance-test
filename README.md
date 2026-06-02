# llm-local-performance-test

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![GitHub stars](https://img.shields.io/github/stars/evilmucedin/llm-local-performance-test?style=social)](https://github.com/evilmucedin/llm-local-performance-test)

**Benchmark your laptop or desktop for local LLMs** — CPU/RAM/GPU probes, quick microbenchmarks, optional live [Ollama](https://ollama.ai) tokens/sec, and a rough **estimated LLM tokens per year**. Includes helpers to wire **Cursor** to Ollama (including over an ngrok tunnel). One dependency: `psutil`.

**Repository:** [github.com/evilmucedin/llm-local-performance-test](https://github.com/evilmucedin/llm-local-performance-test)

## Why use it

- **Comparable numbers** across machines (fixed Ollama `num_ctx` / `num_predict` on the full run).
- **`--simple` mode** — no Ollama required; good for CI or air-gapped checks.
- **`cursor-ollama`** — start/configure Ollama and merge OpenAI-compatible Ollama settings into Cursor’s `settings.json`.
- **Apache-2.0** — use and fork freely.

## Install

```bash
git clone https://github.com/evilmucedin/llm-local-performance-test.git
cd llm-local-performance-test
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Or run from a clone without install (still need `pip install psutil` in your environment):

```bash
python run.py --simple
```

## Run

```bash
# Full run (contacts Ollama API at OLLAMA_HOST if running)
llm-local-perf

python -m llm_local_perf
python run.py

# Lighter path: no Ollama inference
llm-local-perf --simple
```

Environment:

- **`OLLAMA_HOST`** — Ollama base URL (default `http://localhost:11434`).
- **`OLLAMA_BENCH_TIMEOUT`** — per-request timeout for the main benchmark in seconds (default `5800`).

For GPU listing on Linux/NVIDIA, `nvidia-smi` should be on `PATH` if you want discrete VRAM reported.

### Ubuntu Ollama coding-model installer

On Ubuntu/Debian-like machines, use the helper script to install Ollama and pull the best large coding model that fits the current hardware:

```bash
./scripts/install-best-coding-ollama-ubuntu.sh
```

The script queries the Ollama Library for available coding-model tags, reads published model sizes/context windows, checks local NVIDIA VRAM and system RAM, prints the compatibility table, then pulls the highest-priority compatible model. It currently prefers large coding models such as `qwen2.5-coder:32b`, `qwen3-coder:30b`, `codestral:22b`, and `deepseek-coder-v2:16b` when hardware allows them.

Useful overrides:

```bash
DRY_RUN=1 ./scripts/install-best-coding-ollama-ubuntu.sh       # inspect selection only
MODEL=qwen2.5-coder:32b ./scripts/install-best-coding-ollama-ubuntu.sh
GPU_HEADROOM_GB=4 RAM_HEADROOM_GB=8 ./scripts/install-best-coding-ollama-ubuntu.sh
```

### Cursor + Ollama

The **`cursor-ollama`** command ensures a local Ollama daemon, resolves/pulls a model, writes Cursor’s OpenAI-compatible Ollama settings, and optionally launches Cursor.

```bash
cursor-ollama [--no-launch]
cursor-ollama --ollama-host 'https://your-subdomain.ngrok-free.app'   # tunnel URL for Cursor
```

- **`OLLAMA_LOCAL_HOST`** — local API for `ollama serve`, pulls, and health checks (default `http://localhost:11434`).
- **`OLLAMA_HOST`** — base URL stored in Cursor settings; defaults to `OLLAMA_LOCAL_HOST`. Set this to your ngrok (or other) public URL when Cursor must use the tunneled endpoint.
- **`CURSOR_OLLAMA_MODEL`** — default model (default `qwen2.5-coder:7b`).

## Tell others (copy-paste)

Posting is up to you — here is neutral text you can use on [Mastodon](https://joinmastodon.org/), [Bluesky](https://bsky.app/), [X](https://x.com/), [Hacker News](https://news.ycombinator.com/submit), or [Reddit](https://www.reddit.com/r/LocalLLaMA/) (follow each site’s self-promotion rules):

**Short**

> Free Python tool: benchmark your PC for **local LLMs** (Ollama tokens/sec + rough “tokens/year” estimate) + optional Cursor↔Ollama setup. Apache-2.0.  
> https://github.com/evilmucedin/llm-local-performance-test

**Show HN–style title + body**

> **Show HN: llm-local-performance-test — benchmark your machine for local LLM throughput**  
> CLI: microbenchmarks, optional Ollama run with fixed generation settings for fair comparison, naive yearly token estimate. Includes `cursor-ollama` to point Cursor at Ollama (e.g. via ngrok). Python 3.10+, depends only on psutil.

**GitHub “About” topics (set under repo ⚙️)**  
Ideas: `ollama`, `llm`, `benchmark`, `local-llm`, `machine-learning`, `cursor-editor`, `python`, `nvidia`, `inference`

---

*Origins: derived from experimental `llmTest5`-style scripts; this repo is the packaged, maintained form.*

## License

See [LICENSE](LICENSE).
