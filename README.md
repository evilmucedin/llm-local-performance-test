# llm-local-performance-test

Python tool to benchmark a machine (CPU, memory, optional NVIDIA GPU via `nvidia-smi`) and estimate rough **annual LLM token** capacity. The full run optionally calls a local [Ollama](https://ollama.ai) server (`OLLAMA_HOST`, default `http://localhost:11434`) and measures tokens/sec on a small pulled model.

Derived from the `llmTest5` scripts: **`--simple`** matches the original `test1.py` path (microbenchmarks only); the default path matches `test2.py` (adds Ollama runs).

## Install

```bash
cd /path/to/llm-local-performance-test
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
# Full run (Ollama API if reachable)
llm-local-perf

# Same via module
python -m llm_local_perf

# Lighter path: no Ollama inference
llm-local-perf --simple
```

Environment:

- **`OLLAMA_HOST`** — Ollama base URL (default `http://localhost:11434`).
- **`OLLAMA_BENCH_TIMEOUT`** — per-request timeout for the main benchmark in seconds (default `5800`).

Requires **`psutil`**. For GPU listing on Linux/NVIDIA, `nvidia-smi` must be on `PATH` if you want discrete VRAM reported.

### Cursor + Ollama

The **`cursor-ollama`** command ensures a local Ollama daemon, resolves/pulls a model, writes Cursor’s OpenAI-compatible Ollama settings, and optionally launches Cursor.

```bash
cursor-ollama [--no-launch]
cursor-ollama --ollama-host 'https://your-subdomain.ngrok-free.app'   # tunnel URL for Cursor
```

- **`OLLAMA_LOCAL_HOST`** — local API for `ollama serve`, pulls, and health checks (default `http://localhost:11434`).
- **`OLLAMA_HOST`** — base URL stored in Cursor settings; defaults to `OLLAMA_LOCAL_HOST`. Set this to your ngrok (or other) public URL when Cursor must use the tunneled endpoint.
- **`CURSOR_OLLAMA_MODEL`** — default model (default `qwen2.5-coder:7b`).

## License

See [LICENSE](LICENSE).
