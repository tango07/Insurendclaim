#!/usr/bin/env bash
# Installs the project's Claude Code skills and agents into .claude/ (run once from anywhere).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/.claude/skills" "$ROOT/.claude/agents"
cp -R "$ROOT/claude-config/skills/." "$ROOT/.claude/skills/"
cp -R "$ROOT/claude-config/agents/." "$ROOT/.claude/agents/"
echo "Installed into $ROOT/.claude:"
find "$ROOT/.claude" -type f | sed "s|$ROOT/||" | sort
