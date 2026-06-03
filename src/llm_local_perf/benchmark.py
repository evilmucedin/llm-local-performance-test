#!/usr/bin/env python3
"""Full estimator: microbenchmarks plus optional Ollama throughput measurement."""

import json
import os
import platform
import re
import shutil
import subprocess
import time
import urllib.request
from importlib.resources import files

import psutil

from .pricing import CLAUDE_PRICE_LABEL, estimate_hourly_claude_output_cost, format_usd

# Fixed ollama inference settings so all laptops are compared fairly.
# num_ctx=512: tiny KV cache, works on weak/low-RAM hardware.
# num_predict=100: fixed output length → stable tokens/sec measurement.
# temperature=0: deterministic output.
OLLAMA_NUM_CTX = 512
OLLAMA_NUM_PREDICT = 100
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def load_spec_v2() -> str:
    p = files("llm_local_perf").joinpath("data/spec_v2.txt")
    if not p.is_file():
        return "Specification file not found."
    return p.read_text(encoding="utf-8").strip()


def get_system_info():
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
    }


def get_cpu_info():
    freq = psutil.cpu_freq()
    return {
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_cores": psutil.cpu_count(logical=True) or 0,
        "freq_mhz": round(freq.current, 1) if freq else 0.0,
        "usage_percent": psutil.cpu_percent(interval=0.2),
    }


def get_memory_info():
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / (1024**3), 2),
        "available_gb": round(vm.available / (1024**3), 2),
        "used_percent": vm.percent,
    }


def detect_gpu():
    # Apple Silicon: GPU shares unified memory with RAM; no nvidia-smi present.
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        chip = "Apple Silicon"
        try:
            chip = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip() or chip
        except Exception:
            pass
        return [{"name": f"{chip} (unified memory)", "memory_gb": 0.0}]

    # NVIDIA GPU (Linux / Windows)
    if shutil.which("nvidia-smi"):
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            gpus = []
            for line in output.splitlines():
                parts = [x.strip() for x in line.split(",")]
                if len(parts) == 2:
                    gpus.append({"name": parts[0], "memory_gb": round(float(parts[1]) / 1024.0, 2)})
            if gpus:
                return gpus
        except subprocess.CalledProcessError:
            pass

    return [{"name": "No discrete GPU detected", "memory_gb": 0.0}]


def cpu_benchmark(seconds=0.4):
    end = time.perf_counter() + seconds
    x = 1
    loops = 0
    while time.perf_counter() < end:
        x = (x * 1664525 + 1013904223) & 0xFFFFFFFF
        loops += 1
    return loops / seconds


def memory_benchmark(size=6_000_000):
    data = bytearray(b"a" * size)
    start = time.perf_counter()
    copy = data[:]
    elapsed = max(time.perf_counter() - start, 1e-6)
    if copy[0] != data[0]:
        return 0.0
    return (size / (1024 * 1024)) / elapsed


def get_ollama_status():
    ollama_path = shutil.which("ollama")
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        return {
            "installed": ollama_path is not None,
            "usable": True,
            "path": ollama_path,
            "reason": "ok",
        }
    except Exception as exc:
        return {
            "installed": ollama_path is not None,
            "usable": False,
            "path": ollama_path,
            "reason": str(exc),
        }


def parse_model_billion_params(model: str | None, details: dict | None = None) -> float:
    if details:
        parameter_size = str(details.get("parameter_size", ""))
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*b", parameter_size.lower())
        if match:
            return float(match.group(1))

    if not model:
        return 0.0

    match = re.search(r"(?:^|[-_:])([0-9]+(?:\.[0-9]+)?)b(?:$|[-_:])", model.lower())
    return float(match.group(1)) if match else 0.0


def pick_best_local_model():
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    models = [m for m in data.get("models", []) if m.get("name")]
    if not models:
        return None

    non_embedding_models = [
        m for m in models if not any(token in m["name"].lower() for token in ("embed", "embedding"))
    ]
    candidates = non_embedding_models or models

    def score(model):
        name = model["name"]
        details = model.get("details") if isinstance(model.get("details"), dict) else {}
        params = parse_model_billion_params(name, details)
        size_bytes = model.get("size") or 0
        return (params, size_bytes, name)

    return max(candidates, key=score)["name"]


def run_ollama_microbenchmark(timeout_seconds=5800, prompt=None, runs=10, model=None):
    if model is None:
        model = pick_best_local_model()
    if not model:
        return {"ran": False, "model": None, "tokens_per_sec": 0.0, "reason": "No local Ollama model found"}
    print(f"I will use model '{model}'")

    if prompt is None:
        prompt = "Write a short paragraph about laptop performance benchmarking. Keep it factual."

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": 0.0,
        },
    }).encode()

    total_tps = 0.0
    success_count = 0
    last_reason = "ok"

    for i in range(runs):
        try:
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                result = json.loads(resp.read())

            eval_count = result.get("eval_count", 0)
            eval_duration_ns = result.get("eval_duration", 0)
            if eval_count > 0 and eval_duration_ns > 0:
                total_tps += eval_count / (eval_duration_ns / 1e9)
                success_count += 1
            else:
                last_reason = f"Run {i + 1}/{runs}: missing eval stats in response"
        except Exception as exc:
            last_reason = f"Run {i + 1}/{runs} failed: {exc}"

    if success_count == 0:
        return {"ran": False, "model": model, "tokens_per_sec": 0.0, "reason": last_reason}

    return {
        "ran": True,
        "model": model,
        "tokens_per_sec": total_tps / success_count,
        "reason": "ok" if success_count == runs else f"ok ({success_count}/{runs} runs succeeded)",
    }


def estimate_model_throughput_factor(model: str | None) -> float:
    """Return a rough throughput factor inferred from an Ollama model tag.

    The hardware estimator is calibrated around common 7B-class local models.
    Smaller models generally generate more tokens/sec; larger models generally
    generate fewer. If the tag does not expose a size like ``:7b`` or ``-32b``,
    leave the hardware estimate unchanged.
    """
    if not model:
        return 1.0

    billion_params = parse_model_billion_params(model)
    if not billion_params:
        return 1.0
    if billion_params <= 0:
        return 1.0

    return max(0.15, min(3.0, (7.0 / billion_params) ** 0.5))


def estimate_tokens_per_year(cpu, memory, gpus, cpu_ops, mem_mb_s, has_ollama, ollama_tps=0.0, ollama_model=None):
    gpu_mem = sum(g["memory_gb"] for g in gpus)
    model_factor = estimate_model_throughput_factor(ollama_model)
    base = (
        cpu["logical_cores"] * 60
        + memory["total_gb"] * 35
        + gpu_mem * 160
        + (cpu_ops / 10_000)
        + (mem_mb_s * 2)
    )
    if has_ollama:
        base *= 1.1
    if ollama_tps > 0:
        base += ollama_tps * 6
    return int(max(base * model_factor, 1) * 35_000)


def print_quick_view(
    system,
    cpu,
    gpus,
    memory,
    cpu_ops,
    mem_bw,
    ollama_status,
    ollama_bench,
    bench_timeout,
    tokens,
    hourly_claude_cost,
):
    print("\nQuick view:")
    print(f"OS  : {system['os']}")
    print(f"PY  : {system['python']}")
    print(f"PCOR: {cpu['physical_cores']}")
    print(f"LCOR: {cpu['logical_cores']}")
    print(f"CFRQ: {cpu['freq_mhz']}")
    print(f"CUSE: {cpu['usage_percent']}")
    print(f"COPS: {int(cpu_ops):,}")
    print(f"GRAM: {sum(g['memory_gb'] for g in gpus):.2f}")
    print(f"MTOT: {memory['total_gb']}")
    print(f"MAVL: {memory['available_gb']}")
    print(f"MUSE: {memory['used_percent']}")
    print(f"MBWS: {mem_bw:.2f}")
    print(f"OINS: {ollama_status['installed']}")
    print(f"OUSE: {ollama_status['usable']}")
    print(f"ORAN: {ollama_bench['ran']}")
    print(f"OMOD: {ollama_bench['model']}")
    print(f"OMUL: {estimate_model_throughput_factor(ollama_bench['model']):.2f}")
    print(f"OTPS: {ollama_bench['tokens_per_sec']:.2f}")
    print(f"OTMO: {bench_timeout}")
    print(f"TYR : {tokens:,}")
    print(f"T$/H: {format_usd(hourly_claude_cost)}/hr")


def run(ollama_model: str | None = None) -> None:
    spec = load_spec_v2()
    system = get_system_info()
    cpu = get_cpu_info()
    memory = get_memory_info()
    gpus = detect_gpu()
    cpu_ops = cpu_benchmark()
    mem_bw = memory_benchmark()
    ollama_status = get_ollama_status()
    has_ollama = ollama_status["installed"]
    bench_timeout = int(os.getenv("OLLAMA_BENCH_TIMEOUT", "5800"))
    fast_timeout = max(1, bench_timeout // 10)

    selected_ollama_model = ollama_model if ollama_model is not None else None
    if ollama_status["usable"] and selected_ollama_model is None:
        selected_ollama_model = pick_best_local_model()

    fast_ollama_bench = (
        run_ollama_microbenchmark(timeout_seconds=fast_timeout, runs=10, model=selected_ollama_model)
        if ollama_status["usable"]
        else {
            "ran": False,
            "model": selected_ollama_model,
            "tokens_per_sec": 0.0,
            "reason": ollama_status["reason"],
        }
    )
    print("\nOllama fast benchmark result:")
    print(f"  ran: {fast_ollama_bench['ran']}")
    print(f"  model: {fast_ollama_bench['model']}")
    print(f"  tokens_per_sec: {fast_ollama_bench['tokens_per_sec']:.2f}")
    print(f"  timeout_sec: {fast_timeout}")
    print(f"  num_ctx: {OLLAMA_NUM_CTX}")
    print(f"  num_predict: {OLLAMA_NUM_PREDICT}")
    print(f"  reason: {fast_ollama_bench['reason']}")

    ollama_bench = (
        run_ollama_microbenchmark(timeout_seconds=bench_timeout, runs=2, model=selected_ollama_model)
        if ollama_status["usable"]
        else {
            "ran": False,
            "model": selected_ollama_model,
            "tokens_per_sec": 0.0,
            "reason": ollama_status["reason"],
        }
    )
    print("\nOllama benchmark result:")
    print(f"  ran: {ollama_bench['ran']}")
    print(f"  model: {ollama_bench['model']}")
    print(f"  tokens_per_sec: {ollama_bench['tokens_per_sec']:.2f}")
    print(f"  timeout_sec: {bench_timeout}")
    print(f"  num_ctx: {OLLAMA_NUM_CTX}")
    print(f"  num_predict: {OLLAMA_NUM_PREDICT}")
    print(f"  reason: {ollama_bench['reason']}")

    tokens = estimate_tokens_per_year(
        cpu,
        memory,
        gpus,
        cpu_ops,
        mem_bw,
        has_ollama,
        ollama_bench["tokens_per_sec"],
        ollama_bench["model"],
    )

    print("Specification (spec v2):")
    print(spec)
    print("\nSystem:")
    for k, v in system.items():
        print(f"{k}: {v}")
    print("\nCPU:")
    for k, v in cpu.items():
        print(f"{k}: {v}")
    print(f"benchmark_ops_per_sec: {int(cpu_ops):,}")
    print("\nGPU:")
    for g in gpus:
        print(f"name: {g['name']}")
        print(f"memory_gb: {g['memory_gb']}")
    print("\nMemory:")
    for k, v in memory.items():
        print(f"{k}: {v}")
    print(f"bandwidth_mb_per_sec: {mem_bw:.2f}")
    print(f"\nOllama installed: {ollama_status['installed']}")
    print(f"Ollama usable in current runtime: {ollama_status['usable']}")
    print(f"Ollama path: {ollama_status['path']}")
    print(f"Ollama benchmark ran: {ollama_bench['ran']}")
    print(f"Ollama model: {ollama_bench['model']}")
    print(f"Ollama benchmark timeout_sec: {bench_timeout}")
    print(f"Ollama model throughput multiplier: {estimate_model_throughput_factor(ollama_bench['model']):.2f}")
    print(f"Ollama tokens_per_sec: {ollama_bench['tokens_per_sec']:.2f}")
    if not ollama_bench["ran"]:
        print(f"Ollama benchmark note: {ollama_bench['reason']}")
    hourly_claude_cost = estimate_hourly_claude_output_cost(tokens)
    print(f"Estimated LLM tokens per year: {tokens:,}")
    print(f"Estimated {CLAUDE_PRICE_LABEL} per hour: {format_usd(hourly_claude_cost)}/hr")
    print_quick_view(
        system,
        cpu,
        gpus,
        memory,
        cpu_ops,
        mem_bw,
        ollama_status,
        ollama_bench,
        bench_timeout,
        tokens,
        hourly_claude_cost,
    )
