#!/usr/bin/env bash
# Stop hook: before Claude finishes a turn, check the docs still describe the code
# (backend/tests/test_docs_in_sync.py). Exit 2 blocks the stop and sends the failures back to Claude.
input=$(cat)
cd "${CLAUDE_PROJECT_DIR:-.}/backend" || exit 0

out=$(uv run pytest tests/test_docs_in_sync.py -q -p no:cacheprovider 2>&1)
[ $? -eq 0 ] && exit 0

failures=$(echo "$out" | grep -E "AssertionError|FAILED")

# Already blocked once this turn and still failing: let Claude stop, but tell the user.
if echo "$input" | grep -qE '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  echo '{"systemMessage": "Docs are still out of sync with the code. Run: cd backend && uv run pytest tests/test_docs_in_sync.py"}'
  exit 0
fi

{
  echo "The docs are out of sync with the code. Update ARCHITECTURE.md (or the file named below), then finish:"
  echo "$failures"
} >&2
exit 2
