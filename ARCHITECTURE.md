# Architecture

`llm-local-performance-test` is a small Python CLI that estimates local LLM throughput from lightweight hardware probes and, when available, an Ollama generation benchmark.

## Goals

- Run on a fresh Ubuntu-like machine with minimal setup.
- Keep dependencies small (`psutil` only for runtime hardware data).
- Provide two paths:
  - a fast hardware-only estimator for CI, offline, and low-friction runs;
  - a fuller run that also queries Ollama and measures live tokens/sec.
- Print human-readable results that are easy to compare across machines.

## Package layout

```text
run.py                         Convenience launcher from a source checkout
src/llm_local_perf/__main__.py CLI argument parsing
src/llm_local_perf/simple.py   Hardware-only estimator (`--simple`)
src/llm_local_perf/benchmark.py Full estimator with optional Ollama benchmark
src/llm_local_perf/pricing.py  Cloud-token price comparison helpers
src/llm_local_perf/cursor_ollama.py Cursor + Ollama setup helper
src/llm_local_perf/data/       Embedded benchmark scenario/spec text
```

## Execution modes

### Simple mode

Command:

```bash
llm-local-perf --simple
python run.py --simple
```

Flow:

1. Load `data/spec_v1.txt` for the printed scenario.
2. Collect CPU metadata with `psutil` and `/proc/cpuinfo` where available.
3. Try to list NVIDIA GPUs via `nvidia-smi`; otherwise report no NVIDIA GPU.
4. Collect memory totals with `psutil`.
5. Run tiny CPU and memory microbenchmarks.
6. Convert the weighted hardware score into an estimated annual token count.
7. Print the annual token estimate and Claude-equivalent cost per hour.

This path does not contact Ollama and should remain quick and robust.

### Full mode

Command:

```bash
llm-local-perf
python run.py
llm-local-perf --ollama-model qwen2.5-coder:7b
python run.py --ollama-model qwen2.5-coder:7b
```

Flow:

1. Load `data/spec_v2.txt` for the printed scenario.
2. Collect system, CPU, GPU, and memory metadata.
3. Run local CPU and memory microbenchmarks.
4. Check whether Ollama is installed and whether `OLLAMA_HOST` is reachable.
5. If usable, use the model from `--ollama-model` or select the best installed Ollama model, then run Ollama generation benchmarks with fixed settings:
   - `num_ctx = 512`
   - `num_predict = 100`
   - `temperature = 0`
6. Combine hardware score, the Ollama model-size throughput multiplier, and Ollama tokens/sec into an annual token estimate.
7. Print detailed sections plus a compact quick view.
8. Print Claude-equivalent cost per hour beside the token estimate.

If Ollama is not usable, the full mode still completes and explains why the live benchmark was skipped.

## Estimation model

The token estimates are intentionally rough. They are comparison-friendly heuristics, not a guarantee of real production throughput.

Inputs include:

- logical CPU cores;
- total system memory;
- detected discrete GPU memory;
- CPU microbenchmark loops/sec;
- memory copy throughput;
- optional Ollama measured tokens/sec;
- optional Ollama model size parsed from tags like `:7b`, `:32b`, or `:0.5b`.

The full estimator gives extra weight to live Ollama throughput when it is available. It also applies a rough model-size multiplier calibrated around 7B-class models: smaller model tags increase estimated tokens/year, while larger model tags decrease them. The simple estimator uses only hardware-derived signals.

## Claude-equivalent pricing

`pricing.py` converts the annual token estimate into an hourly cloud-token comparison:

```text
annual_tokens -> annual Claude output-token dollars -> dollars/hour
```

The current comparison rate is `CLAUDE_OUTPUT_USD_PER_MILLION_TOKENS = 15.00`, matching commonly quoted Claude Sonnet-tier output-token pricing. Because this project estimates generated tokens, it compares against output-token pricing rather than input-token pricing.

If Claude pricing changes, update `src/llm_local_perf/pricing.py` and mention the new source/rate in the pull request.

## External integrations

### Ollama

The benchmark talks to the Ollama HTTP API at `OLLAMA_HOST`, defaulting to `http://localhost:11434`.

Important endpoints:

- `GET /api/tags` to discover local models. Default selection prefers non-embedding models with the largest parsed parameter count (`details.parameter_size` or tags like `:32b`) or downloaded size.
- `POST /api/generate` to run non-streaming generation and read `eval_count` / `eval_duration`.

### Cursor helper

`cursor-ollama` starts or verifies Ollama, ensures a local model exists, writes Cursor OpenAI-compatible settings, and optionally launches Cursor.

It is intentionally separate from the benchmark path so that benchmark users do not need Cursor installed.

## Output conventions

The CLI prints verbose sections first, then a compact quick view in full mode.

Quick-view abbreviations include:

- `OMOD`: Ollama model.
- `OMUL`: Ollama model throughput multiplier.
- `OTPS`: Ollama tokens/sec.
- `TYR`: estimated tokens/year.
- `T$/H`: Claude-equivalent dollars/hour.

When adding new output, keep both detailed and compact views aligned where possible.

## Error-handling principles

- Hardware probes should degrade gracefully when a platform command is missing.
- Ollama failures should not abort the full benchmark; print the reason and continue with hardware-only estimation.
- Avoid long-running operations in `--simple` mode.
- Keep defaults safe for laptops and CI environments.
