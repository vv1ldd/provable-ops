#!/usr/bin/env bash
# Сборка PDF из Markdown в docs/integrations/
# Требования: brew install pandoc tectonic
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for cmd in pandoc tectonic; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Не найдено: $cmd. Установите: brew install pandoc tectonic"
    exit 1
  fi
done

shopt -s nullglob
for md in docs/integrations/*.md; do
  pdf="${md%.md}.pdf"
  echo "=== $md -> $pdf ==="
  pandoc "$md" -o "$pdf" --pdf-engine=tectonic
done

echo "Готово."
