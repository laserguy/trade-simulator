# Trade Simulator

## Source of truth
- [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md): what we are building (decisions D1, D2, …).
- [WHY.md](WHY.md): why each decision was made (same IDs).
- [ARCHITECTURE.md](ARCHITECTURE.md): where things are in the code (layers, decision → file map, config, tables, endpoints, how to add a provider). Keep it current when files, tables, endpoints or settings change.
- [PROMPT_LOG.md](PROMPT_LOG.md): why each line in the agent prompts is there, what run caused it, and whether it worked. Also lists problems seen in runs that have not led to a change.

## Rules
- Before designing or writing code, read the decision table in PROBLEM_STATEMENT.md to find the D#s the task touches, then read only those `### D#:` entries in WHY.md. Read ARCHITECTURE.md in full before changing code. Skip the decision lookup for small fixes (typos, styling, obvious bugs) that touch no decision. Stay within the current scope.
- When a decision is made or changed, update **both** files in the same step:
  - `PROBLEM_STATEMENT.md`: add or edit the D# row and add a Changelog line with the date.
  - `WHY.md`: add or edit the D# entry (choice, why, alternatives considered, date).
- If code would contradict a decision, stop and ask the user instead of silently deviating.
- Don't build "Parked for later" items unless the user asks.
- Follow the engineering principles D17–D19 and D38 in every change: layers with dependencies pointing inward, tests first, atomic trades, never log API keys, and every external tool behind an app-owned interface, chosen by config and never named in the UI.

## Changing agent prompts
Prompts are not tuned run by run; that goes in circles. Before changing anything in `backend/prompts/*.md`:
- Read the PROMPT_LOG.md entries for the lines involved, so you know why they are there.
- First check whether the app can fix the problem in code, by supplying the information itself. If it can, do that and leave the prompt alone.
- Change a prompt only when the same problem has shown up in **at least three runs**, or when the change is part of a decision (D#) being built. A problem seen in fewer runs goes in PROMPT_LOG.md under "Open observations", with the run's date.
- When reviewing a run, report what you see. Don't attach a prompt change to each finding.
- Every prompt change gets a PROMPT_LOG.md entry in the same step: the line, the run and problem that caused it, and what it is expected to fix. Fill in the result after later runs.

## Commands
- Run backend tests: `cd backend && uv run pytest`
- Doc drift check: `cd backend && uv run pytest tests/test_docs_in_sync.py`. It also runs automatically as a Stop hook (`.claude/settings.json` → `.claude/hooks/check-docs.sh`) and blocks finishing a turn while the docs don't match the code. Fix the docs, not the test.
- Run opt-in tests against real APIs (needs keys in `backend/.env`; costs a little): `cd backend && uv run pytest -m integration`
- Start the app (API + built UI at http://127.0.0.1:8000): `cd backend && uv run trade-sim serve`
- Command-line alternatives: `cd backend && uv run trade-sim status|refresh|run|review`
- Frontend: `cd frontend && npm test` (vitest), `npm run build` (the output is served by `trade-sim serve`), `npm run dev` (Vite on :5173, proxies /api to :8000)
- Model prices shown in Settings: `backend/model_catalogue.json` (update `as_of` when prices change)
- Agent prompts live in `backend/prompts/*.md` (D25); optional MCP servers in `backend/mcp_servers.json` (D27).

## Working style
- Make one decision at a time. Keep information upfront minimal and give a recommendation.
- Agree anything user-facing (screens, layout, what each page shows, style) with the user before building it, and record it in the docs first.
