#!/usr/bin/env bash
# Install Ollama on Ubuntu and pull the best large coding model compatible with
# the current machine. The script queries ollama.com for available coding-model
# tags, reads each tag's published model size, checks local NVIDIA VRAM / RAM,
# then pulls the highest-priority compatible model.
#
# Examples:
#   ./scripts/install-best-coding-ollama-ubuntu.sh
#   DRY_RUN=1 ./scripts/install-best-coding-ollama-ubuntu.sh
#   MODEL=qwen2.5-coder:32b ./scripts/install-best-coding-ollama-ubuntu.sh
#
# Environment:
#   MODEL / OLLAMA_MODEL      Override automatic selection.
#   OLLAMA_HOST               Local Ollama API URL (default: http://127.0.0.1:11434).
#   DRY_RUN=1                 Detect and select, but do not install/start/pull.
#   GPU_HEADROOM_GB=2         Extra VRAM reserved for runtime overhead.
#   RAM_HEADROOM_GB=6         Extra system RAM reserved for runtime overhead.

set -euo pipefail

MODEL_OVERRIDE="${MODEL:-${OLLAMA_MODEL:-}}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_HOST="${OLLAMA_HOST%/}"
OLLAMA_LIBRARY_BASE="${OLLAMA_LIBRARY_BASE:-https://ollama.com}"
DRY_RUN="${DRY_RUN:-0}"
GPU_HEADROOM_GB="${GPU_HEADROOM_GB:-2}"
RAM_HEADROOM_GB="${RAM_HEADROOM_GB:-6}"

# Ordered by coding-model preference, not just size. Fallback sizes are only used
# when the Ollama Library page cannot be parsed; normally the script reads live
# tag sizes from ollama.com/library/<model>/tags.
read -r -d '' MODEL_CANDIDATES <<'EOF' || true
110|qwen3-coder:480b|290|Qwen3-Coder flagship MoE; only for very large local memory
100|qwen2.5-coder:32b|20|Best dense local coding default when hardware allows it
96|qwen3-coder:30b|19|Large long-context agentic coding model
92|codestral:22b|13|Large Mistral code-generation model
90|deepseek-coder-v2:16b|8.9|Strong mid-large code model for 12-16 GB GPUs
86|qwen2.5-coder:14b|9.0|High-quality Qwen coder for mid-range hardware
82|starcoder2:15b|9.1|Transparent open code model, useful fallback
78|qwen2.5-coder:7b|4.7|Best compact Qwen coder for 8 GB GPUs
74|codegemma:7b|5.0|Compact dedicated coding fallback
70|qwen2.5-coder:3b|1.9|Small coding fallback for constrained machines
65|qwen2.5-coder:1.5b|1.0|Very small coding fallback
60|qwen2.5-coder:0.5b|0.4|Last-resort coding fallback
EOF

log() { printf '\n==> %s\n' "$*"; }
warn() { printf '\nWARNING: %s\n' "$*" >&2; }

need_sudo() {
  if [[ "${EUID}" -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || {
      echo "This script needs sudo for package/Ollama installation." >&2
      exit 1
    }
    echo sudo
  fi
}

ensure_ubuntu_like() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    case "${ID:-} ${ID_LIKE:-}" in
      *ubuntu*|*debian*) return 0 ;;
    esac
  fi
  warn "This script is intended for Ubuntu/Debian-like Linux; continuing anyway."
}

ensure_curl() {
  if command -v curl >/dev/null 2>&1; then
    return 0
  fi

  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "curl is required to query the Ollama Library; install curl or unset DRY_RUN to let the script install it." >&2
    exit 1
  fi

  local sudo_cmd
  sudo_cmd="$(need_sudo)"
  log "Installing curl"
  ${sudo_cmd} apt-get update
  ${sudo_cmd} apt-get install -y curl ca-certificates
}

install_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    log "Ollama already installed: $(command -v ollama)"
    return 0
  fi

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY_RUN=1: skipping Ollama installation"
    return 0
  fi

  ensure_curl
  log "Installing Ollama"
  curl -fsSL "${OLLAMA_LIBRARY_BASE}/install.sh" | sh
}

start_ollama() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY_RUN=1: skipping Ollama startup"
    return 0
  fi

  if curl -fsS "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    log "Ollama API already reachable at ${OLLAMA_HOST}"
    return 0
  fi

  log "Starting Ollama"
  if command -v systemctl >/dev/null 2>&1; then
    local sudo_cmd
    sudo_cmd="$(need_sudo)"
    ${sudo_cmd} systemctl enable --now ollama || true
  fi

  if ! curl -fsS "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  fi

  for _ in {1..30}; do
    if curl -fsS "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
      log "Ollama API is ready at ${OLLAMA_HOST}"
      return 0
    fi
    sleep 1
  done

  echo "Ollama did not become reachable at ${OLLAMA_HOST}. See /tmp/ollama-serve.log if started manually." >&2
  exit 1
}

ceil_gb_from_mib() {
  local mib="$1"
  echo $(( (mib + 1023) / 1024 ))
}

detect_max_nvidia_vram_gb() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo 0
    return 0
  fi

  local max_mib=0 line
  while IFS= read -r line; do
    line="${line//[!0-9]/}"
    [[ -z "${line}" ]] && continue
    (( line > max_mib )) && max_mib="${line}"
  done < <(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null || true)

  ceil_gb_from_mib "${max_mib}"
}

detect_total_ram_gb() {
  local kib bytes
  kib="$(awk '/MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
  if [[ "${kib}" =~ ^[0-9]+$ ]] && (( kib > 0 )); then
    echo $(( (kib + 1024 * 1024 - 1) / (1024 * 1024) ))
    return 0
  fi

  # Non-Ubuntu fallback keeps DRY_RUN useful when validating the script elsewhere.
  bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
  if [[ "${bytes}" =~ ^[0-9]+$ ]] && (( bytes > 0 )); then
    echo $(( (bytes + 1024 * 1024 * 1024 - 1) / (1024 * 1024 * 1024) ))
    return 0
  fi

  echo 0
}

fetch_url() {
  local url="$1"
  curl -fsSL --retry 2 --connect-timeout 8 --max-time 30 "$url"
}

parse_tag_metadata() {
  local model_ref="$1" fallback_size_gb="$2"

  if ! command -v python3 >/dev/null 2>&1; then
    printf '%s|unknown\n' "${fallback_size_gb}"
    return 0
  fi

  OLLAMA_TAG_HTML="$(cat)" python3 - "$model_ref" "$fallback_size_gb" <<'PY'
import os
import re
import sys

model = sys.argv[1]
fallback_size = sys.argv[2]
text = os.environ.get("OLLAMA_TAG_HTML", "")
plain = re.sub(r"<[^>]+>", " ", text)
plain = re.sub(r"\s+", " ", plain)

size_gb = fallback_size
context = "unknown"
idx = plain.find(model)
if idx >= 0:
    window = plain[idx:idx + 500]
    size_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(GB|MB)\b", window, re.I)
    if size_match:
        amount = float(size_match.group(1))
        unit = size_match.group(2).upper()
        size_gb = amount if unit == "GB" else amount / 1024.0
        size_gb = f"{size_gb:.2f}".rstrip("0").rstrip(".")
    context_match = re.search(r"([0-9]+(?:\.[0-9]+)?\s*[KMG]?)\s*context window", window, re.I)
    if context_match:
        context = context_match.group(1).replace(" ", "")

print(f"{size_gb}|{context}")
PY
}

model_family() {
  local model_ref="$1"
  echo "${model_ref%%:*}"
}

remote_model_available() {
  local model_ref="$1" search_html="$2" tags_html="$3"
  local family
  family="$(model_family "${model_ref}")"

  grep -Fqi "${family}" <<<"${search_html}" && grep -Fq "${model_ref}" <<<"${tags_html}"
}

discover_available_models() {
  local search_html="" rank model_ref fallback_size note family tags_html metadata size context

  search_html="$(fetch_url "${OLLAMA_LIBRARY_BASE}/search?q=code" 2>/dev/null || true)"
  if [[ -z "${search_html}" ]]; then
    warn "Could not query Ollama Library search. Falling back to the built-in candidate table."
  fi

  while IFS='|' read -r rank model_ref fallback_size note; do
    [[ -z "${rank}" ]] && continue
    family="$(model_family "${model_ref}")"
    tags_html="$(fetch_url "${OLLAMA_LIBRARY_BASE}/library/${family}/tags" 2>/dev/null || true)"

    if [[ -n "${search_html}" && -n "${tags_html}" ]]; then
      if ! remote_model_available "${model_ref}" "${search_html}" "${tags_html}"; then
        continue
      fi
      metadata="$(parse_tag_metadata "${model_ref}" "${fallback_size}" <<<"${tags_html}")"
      size="${metadata%%|*}"
      context="${metadata#*|}"
      printf '%s|%s|%s|%s|%s\n' "${rank}" "${model_ref}" "${size}" "${context}" "${note}"
    else
      printf '%s|%s|%s|unknown|%s\n' "${rank}" "${model_ref}" "${fallback_size}" "${note}"
    fi
  done <<<"${MODEL_CANDIDATES}"
}

float_le() {
  awk -v a="$1" -v b="$2" 'BEGIN { exit !(a <= b) }'
}

add_float() {
  awk -v a="$1" -v b="$2" 'BEGIN { printf "%.2f", a + b }'
}

compatibility_reason() {
  local size_gb="$1" vram_gb="$2" ram_gb="$3"
  local gpu_required ram_required
  gpu_required="$(add_float "${size_gb}" "${GPU_HEADROOM_GB}")"
  ram_required="$(add_float "${size_gb}" "${RAM_HEADROOM_GB}")"

  if (( vram_gb > 0 )) && float_le "${gpu_required}" "${vram_gb}"; then
    printf 'fits GPU: %.2f GB model + %s GB headroom <= %s GB VRAM' "${size_gb}" "${GPU_HEADROOM_GB}" "${vram_gb}"
    return 0
  fi

  if float_le "${ram_required}" "${ram_gb}"; then
    printf 'fits RAM/CPU: %.2f GB model + %s GB headroom <= %s GB RAM' "${size_gb}" "${RAM_HEADROOM_GB}" "${ram_gb}"
    return 0
  fi

  printf 'too large: %.2f GB model needs >%s GB VRAM or >%s GB RAM with configured headroom' \
    "${size_gb}" "${gpu_required}" "${ram_required}"
  return 1
}

select_model() {
  local available="$1" vram_gb="$2" ram_gb="$3"
  local rank model_ref size_gb context note reason

  if [[ -n "${MODEL_OVERRIDE}" ]]; then
    printf '0|%s|manual|unknown|manual override via MODEL/OLLAMA_MODEL\n' "${MODEL_OVERRIDE}"
    return 0
  fi

  while IFS='|' read -r rank model_ref size_gb context note; do
    [[ -z "${rank}" ]] && continue
    if reason="$(compatibility_reason "${size_gb}" "${vram_gb}" "${ram_gb}")"; then
      printf '%s|%s|%s|%s|%s; %s\n' "${rank}" "${model_ref}" "${size_gb}" "${context}" "${note}" "${reason}"
      return 0
    fi
  done <<<"${available}"

  echo "No compatible Ollama coding model candidate found for ${vram_gb} GB VRAM / ${ram_gb} GB RAM." >&2
  exit 1
}

print_available_models() {
  local available="$1" vram_gb="$2" ram_gb="$3"
  local rank model_ref size_gb context note reason status

  log "Available Ollama coding candidates and hardware compatibility"
  printf '%-24s %-8s %-9s %-12s %s\n' "MODEL" "SIZE" "CONTEXT" "STATUS" "NOTE"
  while IFS='|' read -r rank model_ref size_gb context note; do
    [[ -z "${rank}" ]] && continue
    if reason="$(compatibility_reason "${size_gb}" "${vram_gb}" "${ram_gb}")"; then
      status="compatible"
    else
      status="skip"
    fi
    printf '%-24s %-8s %-9s %-12s %s (%s)\n' "${model_ref}" "${size_gb}GB" "${context}" "${status}" "${note}" "${reason}"
  done <<<"${available}"
}

pull_model() {
  local model="$1"
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY_RUN=1: would pull coding model: ${model}"
    return 0
  fi

  log "Pulling coding model: ${model}"
  ollama pull "${model}"
}

print_summary() {
  local selected="$1" vram_gb="$2" ram_gb="$3"
  local _rank model size context reason
  IFS='|' read -r _rank model size context reason <<<"${selected}"

  cat <<EOF

Done.
Selected model : ${model}
Model size     : ${size} GB
Context        : ${context}
Why selected   : ${reason}
NVIDIA VRAM    : ${vram_gb} GB (largest detected GPU; 0 means none detected)
System RAM     : ${ram_gb} GB
Ollama host    : ${OLLAMA_HOST}

Try it:
  ollama run ${model}

Use with this repository:
  OLLAMA_HOST=${OLLAMA_HOST} CURSOR_OLLAMA_MODEL=${model} cursor-ollama --no-launch
  OLLAMA_HOST=${OLLAMA_HOST} python run.py

Override automatic selection:
  MODEL=qwen2.5-coder:32b $0
EOF
}

main() {
  ensure_ubuntu_like
  ensure_curl

  local vram_gb ram_gb available selected model
  vram_gb="$(detect_max_nvidia_vram_gb)"
  ram_gb="$(detect_total_ram_gb)"

  log "Detected largest NVIDIA VRAM: ${vram_gb} GB"
  log "Detected system RAM: ${ram_gb} GB"

  available="$(discover_available_models)"
  if [[ -z "${available}" ]]; then
    echo "No Ollama coding models were discovered from ${OLLAMA_LIBRARY_BASE}." >&2
    exit 1
  fi

  print_available_models "${available}" "${vram_gb}" "${ram_gb}"
  selected="$(select_model "${available}" "${vram_gb}" "${ram_gb}")"
  model="$(cut -d'|' -f2 <<<"${selected}")"

  log "Selected best-fit coding model: ${model}"
  if (( vram_gb == 0 )); then
    warn "No NVIDIA GPU was detected. The selected model may run on CPU and can be slow."
  fi

  install_ollama
  start_ollama
  pull_model "${model}"
  print_summary "${selected}" "${vram_gb}" "${ram_gb}"
}

main "$@"
