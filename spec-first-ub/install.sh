#!/usr/bin/env bash
# Instala spec-first-ub no Claude Code via symlinks (seguro rodar várias vezes).
# Uso: ./install.sh [--uninstall]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SKILL_LINK="$CLAUDE_DIR/skills/spec-first-ub"
CMD_DIR="$CLAUDE_DIR/commands"

is_ours() { [ -L "$1" ] && [[ "$(readlink "$1")" == "$REPO"* ]]; }

if [ "${1:-}" = "--uninstall" ]; then
  for f in "$REPO"/commands/*.md; do
    t="$CMD_DIR/$(basename "$f")"
    if is_ours "$t"; then rm "$t"; echo "removido $t"; fi
  done
  if is_ours "$SKILL_LINK"; then rm "$SKILL_LINK"; echo "removido $SKILL_LINK"; fi
  exit 0
fi

mkdir -p "$CMD_DIR" "$CLAUDE_DIR/skills"

link() { # link <origem> <destino>
  local src="$1" dst="$2"
  if [ -e "$dst" ] && ! is_ours "$dst"; then
    echo "AVISO: $dst já existe e não é link deste repositório; ignorado (remova-o para instalar)" >&2
    return
  fi
  ln -sfn "$src" "$dst"
  echo "ok $dst -> $src"
}

link "$REPO" "$SKILL_LINK"
for f in "$REPO"/commands/*.md; do
  link "$f" "$CMD_DIR/$(basename "$f")"
done
