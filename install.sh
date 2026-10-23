#!/usr/bin/env bash
set -euo pipefail

virion_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
virion_codex=false
case "${1:-}" in
    "") ;;
    --codex) virion_codex=true ;;
    *) echo 'Usage: bash install.sh [--codex]' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then echo 'Too many arguments' >&2; exit 2; fi
if "$virion_codex"; then
    command -v codex >/dev/null || { echo 'Install Codex CLI first.' >&2; exit 2; }
    if codex mcp get plum-virion >/dev/null 2>&1; then
        echo 'Codex already has plum-virion. Existing registration preserved; use codex mcp remove plum-virion before changing it.' >&2
        exit 2
    fi
fi
python3 -m venv "$virion_root/.venv"
"$virion_root/.venv/bin/python" -m pip install -e "$virion_root"
if [ ! -e "$virion_root/config.yaml" ]; then
    install -m 600 "$virion_root/config.yaml.sample" "$virion_root/config.yaml"
fi
if "$virion_codex"; then
    codex mcp add plum-virion -- "$virion_root/.venv/bin/plum-virion" --config "$virion_root/config.yaml"
fi
echo 'Installed. Fill config.yaml, then run .venv/bin/plum-virion --config config.yaml --check.'
