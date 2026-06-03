"""CLI: full benchmark by default; `--simple` for the lighter path without Ollama."""

import argparse

from llm_local_perf import __version__
from llm_local_perf.benchmark import run as run_full
from llm_local_perf.simple import run as run_simple


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate local LLM token throughput: hardware probes, microbenchmarks, optional Ollama."
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Run the v1 estimator only (CPU/GPU/RAM microbenchmarks, no Ollama API).",
    )
    parser.add_argument(
        "--ollama-model",
        metavar="MODEL",
        help="Use this Ollama model for the full benchmark instead of selecting the best installed model.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args()
    if args.simple:
        run_simple()
    else:
        run_full(ollama_model=args.ollama_model)


if __name__ == "__main__":
    main()
