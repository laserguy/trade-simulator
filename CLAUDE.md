# Trade Simulator

## Source of truth
- [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md): what we are building (decisions D1, D2, …).
- [WHY.md](WHY.md): why each decision was made (same IDs).
- [ARCHITECTURE.md](ARCHITECTURE.md): where things are in the code (layers, decision → file map, config, tables, endpoints, how to add a provider). Keep it current when files, tables, endpoints or settings change.

## Rules
- Read PROBLEM_STATEMENT.md and WHY.md before designing or writing code, and ARCHITECTURE.md before changing code. Stay within the current scope.
- When a decision is made or changed, update **both** files in the same step:
  - `PROBLEM_STATEMENT.md`: add or edit the D# row and add a Changelog line with the date.
  - `WHY.md`: add or edit the D# entry (choice, why, alternatives considered, date).
- If code would contradict a decision, stop and ask the user instead of silently deviating.
- Don't build "Parked for later" items unless the user asks.
- Follow the engineering principles D17–D19 and D38 in every change: layers with dependencies pointing inward, tests first, atomic trades, never log API keys, and every external tool behind an app-owned interface, chosen by config and never named in the UI.

## Commands
- Run backend tests: `cd backend && uv run pytest`
- Doc drift check: `cd backend && uv run pytest tests/test_docs_in_sync.py`. It also runs automatically as a Stop hook (`.claude/settings.json` → `.claude/hooks/check-docs.sh`) and blocks finishing a turn while the docs don't match the code. Fix the docs, not the test.
- Run opt-in tests against real APIs (needs keys in `backend/.env`; costs a little): `cd backend && uv run pytest -m integration`
- Start the app (API + built UI at http://127.0.0.1:8000): `cd backend && uv run trade-sim serve`
- Command-line alternatives: `cd backend && uv run trade-sim status|refresh|run`
- Frontend: `cd frontend && npm test` (vitest), `npm run build` (the output is served by `trade-sim serve`), `npm run dev` (Vite on :5173, proxies /api to :8000)
- Model prices shown in Settings: `backend/model_catalogue.json` (update `as_of` when prices change)
- Agent prompts live in `backend/prompts/*.md` (D25); optional MCP servers in `backend/mcp_servers.json` (D27).

## Working style
- Make one decision at a time. Keep information upfront minimal and give a recommendation.
- Agree anything user-facing (screens, layout, what each page shows, style) with the user before building it, and record it in the docs first.
