#!/usr/bin/env bash
set -euo pipefail

skip_live_guard=0
skip_openai_probe=0
skip_serve=0
port=8788

while (($#)); do
  case "$1" in
    --skip-live-guard) skip_live_guard=1 ;;
    --skip-openai-probe) skip_openai_probe=1 ;;
    --skip-serve) skip_serve=1 ;;
    --port) shift; port="${1:?--port needs a value}" ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_root="$repo_root/demo-output"
cd "$repo_root"
if [[ -x "$repo_root/.venv/bin/python" ]]; then
  claw_cmd=("$repo_root/.venv/bin/python" -m clawreinforce)
elif [[ -x "$repo_root/.venv/Scripts/python.exe" ]]; then
  claw_cmd=("$repo_root/.venv/Scripts/python.exe" -m clawreinforce)
elif command -v python >/dev/null && python -c 'import clawreinforce' >/dev/null 2>&1; then
  claw_cmd=(python -m clawreinforce)
elif command -v clawreinforce >/dev/null; then
  claw_cmd=(clawreinforce)
else
  echo 'Install first: python -m pip install -e . (or install it in .venv).' >&2
  exit 1
fi
if [[ ! -d "$output_root" ]]; then
  mkdir "$output_root"
fi

capture_claw() {
  local allowed="$1"
  shift
  printf '\n> clawreinforce' >&2
  printf ' %q' "$@" >&2
  printf '\n' >&2
  set +e
  local output
  output="$("${claw_cmd[@]}" "$@" 2>&1)"
  local status=$?
  set -e
  printf '%s\n' "$output" >&2
  case ",$allowed," in
    *",$status,"*) ;;
    *) echo "clawreinforce exited with $status" >&2; return "$status" ;;
  esac
  printf '%s' "$output"
}

printf '\n[1/4] Guard a real ClawHub skill\n'
if ((skip_live_guard)); then
  echo 'SKIPPED (--skip-live-guard). Expected: review; reason: skill has no golden cases.'
else
  guard_json="$(capture_claw '0,2' guard 'https://clawhub.ai/jaaneek/skills/x-search' --tier 'openai:gpt-5.6-sol')"
  printf '%s' "$guard_json" | python -c 'import json,sys; d=json.load(sys.stdin); assert d["verdict"] == "review" and "skill has no golden cases" in d["reasons"]'
fi
echo 'Guard cost: $0.00 — no golden cases means no model request.'
if ((!skip_openai_probe)) && [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo 'Optional paid connectivity proof; typically under $0.01 at current GPT-5.6 Sol rates.'
  capture_claw '0' models --project . --probe 'openai:gpt-5.6-sol' >/dev/null
elif ((!skip_openai_probe)); then
  echo 'OPENAI_API_KEY is absent; skipping the optional paid probe.'
fi

printf '\n[2/4] Certify and render signed evidence (zero keys)\n'
certify_json="$(capture_claw '0' certify examples/incident-triage-skill --tier fixture:reference)"
printf '%s' "$certify_json" | python -c 'import json,sys; assert json.load(sys.stdin)["report"]["tiers"][0]["pass_rate"] == 1.0'
certificate="$output_root/incident-triage-certificate.json"
printf '%s' "$certify_json" | python -c 'import json,shutil,sys; shutil.copyfile(json.load(sys.stdin)["certificate_path"], sys.argv[1])' "$certificate"
badge="$output_root/incident-triage-badge.svg"
capture_claw '0' badge "$certificate" --output "$badge" >/dev/null

printf '\n[3/4] Measure uplift and export evidence (zero keys)\n'
csv="$output_root/arena.csv"
png="$output_root/arena.png"
bench_json="$(capture_claw '0' bench examples/incident-triage-task examples/incident-triage-skill --tier fixture:reference --trials 2 --csv "$csv" --png "$png")"
printf '%s' "$bench_json" | python -c 'import json,sys; assert json.load(sys.stdin)["report"]["summary"]["uplift"] == 1.0'
for artifact in "$certificate" "$badge" "$csv" "$png"; do
  [[ -s "$artifact" ]] || { echo "Missing demo artifact: $artifact" >&2; exit 1; }
done
echo "Artifacts ready in $output_root"

printf '\n[4/4] Open the four-tab GUI\n'
echo "Open http://127.0.0.1:$port and follow docs/DEMO.md."
if ((skip_serve)); then
  echo 'SKIPPED (--skip-serve).'
else
  "${claw_cmd[@]}" serve --project . --host 127.0.0.1 --port "$port"
fi
