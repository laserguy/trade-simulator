"""SQLite implementation of the Repository port (D15).

Money is stored as TEXT so Decimal values round-trip exactly. Timestamps are stored as UTC ISO-8601.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from trade_simulator.application.ports import (
    BenchmarkStart,
    DailyBar,
    ExecutedTrade,
    MarketOverview,
    PriceSync,
    ValueSnapshot,
)
from trade_simulator.core.decision_log import (
    DecisionRun,
    Finding,
    RunCost,
    RunStatus,
    RunTrigger,
    Watchlist,
    WatchlistEntry,
)
from trade_simulator.core.errors import StorageError
from trade_simulator.core.order import Order, Side
from trade_simulator.core.portfolio import Portfolio, Position
from trade_simulator.core.strategy import Strategy, StrategySection, StrategyVersion
from trade_simulator.core.strategy_review import (
    ClosedTrade,
    Followed,
    HoldingResult,
    OrderOutcome,
    ReviewDecision,
    ReviewTrigger,
    Scorecard,
    StockMove,
    StrategyReview,
    TargetsVerdict,
    TradingDay,
)
from trade_simulator.core.trading_rules import OrderResult, OrderStatus, RejectionReason

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    cash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL,
    average_cost TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    trigger TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    failure_reason TEXT,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    searches INTEGER NOT NULL,
    trace_id TEXT,
    model TEXT,
    strategy_version INTEGER
);
CREATE INDEX IF NOT EXISTS runs_started_at ON runs (started_at);
CREATE TABLE IF NOT EXISTS findings (
    run_id TEXT NOT NULL REFERENCES runs (id),
    seq INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    summary TEXT NOT NULL,
    sources TEXT NOT NULL,
    warnings TEXT NOT NULL,
    price TEXT,
    change_percent TEXT,
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS order_results (
    run_id TEXT NOT NULL REFERENCES runs (id),
    seq INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    price TEXT,
    fee TEXT,
    rejection_reason TEXT,
    strategy_section TEXT,
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS watchlist_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    refreshed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist_entries (
    seq INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    reason TEXT NOT NULL,
    sources TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS value_snapshots (
    at TEXT PRIMARY KEY,
    total_value TEXT NOT NULL,
    benchmark_price TEXT NOT NULL,
    cash TEXT
);
CREATE TABLE IF NOT EXISTS price_history (
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    day TEXT NOT NULL,
    open TEXT NOT NULL,
    high TEXT NOT NULL,
    low TEXT NOT NULL,
    close TEXT NOT NULL,
    adj_close TEXT NOT NULL,
    volume INTEGER NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (exchange, symbol, day)
);
CREATE TABLE IF NOT EXISTS price_history_sync (
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    first_day TEXT,
    last_day TEXT,
    last_checked_at TEXT NOT NULL,
    PRIMARY KEY (exchange, symbol)
);
CREATE TABLE IF NOT EXISTS benchmark_start (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    symbol TEXT NOT NULL,
    price TEXT NOT NULL,
    started_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategy_reviews (
    id TEXT PRIMARY KEY,
    trigger TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    failure_reason TEXT,
    reviewed_version INTEGER,
    decision TEXT,
    reason TEXT NOT NULL,
    targets_verdict TEXT,
    targets_note TEXT NOT NULL,
    followed TEXT,
    followed_note TEXT NOT NULL,
    section_changes TEXT NOT NULL,
    scorecard TEXT,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    model TEXT,
    trace_id TEXT
);
CREATE TABLE IF NOT EXISTS strategy_versions (
    number INTEGER PRIMARY KEY,
    what_i_look_for TEXT NOT NULL,
    position_size TEXT NOT NULL,
    when_i_sell TEXT NOT NULL,
    cash_and_pace TEXT NOT NULL,
    targets TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    review_id TEXT NOT NULL REFERENCES strategy_reviews (id)
);
"""

# Columns added after the first release, applied to existing databases on start-up.
_ADDED_COLUMNS = {
    "runs": {"model": "TEXT", "strategy_version": "INTEGER"},
    "findings": {"price": "TEXT", "change_percent": "TEXT"},
    "order_results": {"strategy_section": "TEXT"},
    "value_snapshots": {"cash": "TEXT"},
}


class SqliteRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        with self._transaction() as conn:
            conn.executescript(_SCHEMA)
            for table, columns in _ADDED_COLUMNS.items():
                existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
                for column, column_type in columns.items():
                    if column not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    # --- settings (D9) ---

    def load_settings(self) -> dict[str, str]:
        with self._transaction() as conn:
            return {key: value for key, value in conn.execute("SELECT key, value FROM settings")}

    def save_setting(self, key: str, value: str | None) -> None:
        with self._transaction() as conn:
            if value is None:
                conn.execute("DELETE FROM settings WHERE key = ?", (key,))
            else:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    # --- value history (D33) ---

    def save_value_snapshot(self, snapshot: ValueSnapshot) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO value_snapshots (at, total_value, benchmark_price, cash) VALUES (?, ?, ?, ?)",
                (_to_iso(snapshot.at), str(snapshot.total_value), str(snapshot.benchmark_price),
                 _decimal_text(snapshot.cash)),
            )

    def load_value_snapshots(self) -> list[ValueSnapshot]:
        with self._transaction() as conn:
            rows = conn.execute("SELECT at, total_value, benchmark_price, cash FROM value_snapshots ORDER BY at").fetchall()
        return [
            ValueSnapshot(_from_iso(r["at"]), Decimal(r["total_value"]), Decimal(r["benchmark_price"]),
                          _decimal_or_none(r["cash"]))
            for r in rows
        ]

    # --- price history (D36) ---

    def save_daily_bars(self, exchange: str, symbol: str, bars: list[DailyBar], source: str) -> None:
        with self._transaction() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO price_history
                   (exchange, symbol, day, open, high, low, close, adj_close, volume, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (exchange, symbol, b.day.isoformat(), str(b.open), str(b.high), str(b.low),
                     str(b.close), str(b.adj_close), b.volume, source)
                    for b in bars
                ],
            )

    def load_daily_bars(self, exchange: str, symbol: str, since: date) -> list[DailyBar]:
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT day, open, high, low, close, adj_close, volume FROM price_history
                   WHERE exchange = ? AND symbol = ? AND day >= ? ORDER BY day""",
                (exchange, symbol, since.isoformat()),
            ).fetchall()
        return [
            DailyBar(date.fromisoformat(r["day"]), Decimal(r["open"]), Decimal(r["high"]), Decimal(r["low"]),
                     Decimal(r["close"]), Decimal(r["adj_close"]), r["volume"])
            for r in rows
        ]

    def save_price_sync(self, sync: PriceSync) -> None:
        with self._transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO price_history_sync
                   (exchange, symbol, first_day, last_day, last_checked_at) VALUES (?, ?, ?, ?, ?)""",
                (sync.exchange, sync.symbol, _date_text(sync.first_day), _date_text(sync.last_day),
                 _to_iso(sync.last_checked_at)),
            )

    def load_price_sync(self, exchange: str, symbol: str) -> PriceSync | None:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM price_history_sync WHERE exchange = ? AND symbol = ?", (exchange, symbol)
            ).fetchone()
        if row is None:
            return None
        return PriceSync(
            exchange, symbol, _date_or_none(row["first_day"]), _date_or_none(row["last_day"]),
            _from_iso(row["last_checked_at"]),
        )

    def executed_trades(self, symbol: str | None = None) -> list[ExecutedTrade]:
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT r.started_at, o.side, o.quantity, o.price, o.run_id, o.symbol, o.reason
                   FROM order_results o JOIN runs r ON r.id = o.run_id
                   WHERE (? IS NULL OR o.symbol = ?) AND o.status = ? ORDER BY r.started_at, o.seq""",
                (symbol, symbol, OrderStatus.EXECUTED.value),
            ).fetchall()
        return [ExecutedTrade(_from_iso(r[0]), Side(r[1]), r[2], Decimal(r[3]), r[4], r[5], r[6]) for r in rows]

    # --- benchmark (D23) ---

    def load_benchmark_start(self) -> BenchmarkStart | None:
        with self._transaction() as conn:
            row = conn.execute("SELECT symbol, price, started_at FROM benchmark_start WHERE id = 1").fetchone()
        if row is None:
            return None
        return BenchmarkStart(row["symbol"], Decimal(row["price"]), _from_iso(row["started_at"]))

    def save_benchmark_start(self, symbol: str, price: Decimal, started_at: datetime) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO benchmark_start (id, symbol, price, started_at) VALUES (1, ?, ?, ?)",
                (symbol, str(price), _to_iso(started_at)),
            )

    # --- portfolio ---

    def load_portfolio(self) -> Portfolio | None:
        with self._transaction() as conn:
            row = conn.execute("SELECT cash FROM portfolio WHERE id = 1").fetchone()
            if row is None:
                return None
            positions = {
                symbol: Position(symbol, quantity, Decimal(cost))
                for symbol, quantity, cost in conn.execute(
                    "SELECT symbol, quantity, average_cost FROM positions"
                )
            }
        return Portfolio(cash=Decimal(row[0]), positions=positions)

    def save_portfolio(self, portfolio: Portfolio) -> None:
        with self._transaction() as conn:
            _write_portfolio(conn, portfolio)

    # --- runs ---

    def save_run(self, run: DecisionRun, portfolio: Portfolio | None) -> None:
        with self._transaction() as conn:
            if portfolio is not None:
                _write_portfolio(conn, portfolio)
            _write_run(conn, run)

    def get_run(self, run_id: str) -> DecisionRun | None:
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            return _read_run(conn, row) if row else None

    def list_runs(self, limit: int = 50) -> list[DecisionRun]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [_read_run(conn, row) for row in rows]

    def latest_market_overview(self) -> MarketOverview | None:
        with self._transaction() as conn:
            row = conn.execute(
                """SELECT r.started_at, f.summary, f.sources FROM runs r
                   JOIN findings f ON f.run_id = r.id
                   WHERE r.trigger = ? AND r.status = ? AND f.symbol = 'MARKET'
                   ORDER BY r.started_at DESC LIMIT 1""",
                (RunTrigger.REFRESH.value, RunStatus.COMPLETED.value),
            ).fetchone()
        if row is None:
            return None
        return MarketOverview(row["summary"], tuple(json.loads(row["sources"])), _from_iso(row["started_at"]))

    # --- strategies (D43) ---

    def save_strategy_review(self, review: StrategyReview, new_version: StrategyVersion | None) -> None:
        with self._transaction() as conn:
            _write_strategy_review(conn, review)
            if new_version is not None:
                conn.execute(
                    "UPDATE strategy_versions SET ended_at = ? WHERE ended_at IS NULL",
                    (_to_iso(new_version.started_at),),
                )
                _write_strategy_version(conn, new_version)

    def current_strategy(self) -> StrategyVersion | None:
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM strategy_versions WHERE ended_at IS NULL").fetchone()
        return _read_strategy_version(row) if row else None

    def runs_following(self, version: int) -> list[DecisionRun]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE strategy_version = ? ORDER BY started_at", (version,)
            ).fetchall()
            return [_read_run(conn, row) for row in rows]

    def strategy_versions(self) -> list[StrategyVersion]:
        with self._transaction() as conn:
            rows = conn.execute("SELECT * FROM strategy_versions ORDER BY number").fetchall()
        return [_read_strategy_version(row) for row in rows]

    def strategy_reviews(self) -> list[StrategyReview]:
        with self._transaction() as conn:
            rows = conn.execute("SELECT * FROM strategy_reviews ORDER BY started_at").fetchall()
        return [_read_strategy_review(row) for row in rows]

    # --- watchlist ---

    def load_watchlist(self) -> Watchlist | None:
        with self._transaction() as conn:
            meta = conn.execute("SELECT refreshed_at FROM watchlist_meta WHERE id = 1").fetchone()
            if meta is None:
                return None
            entries = tuple(
                WatchlistEntry(symbol, reason, tuple(json.loads(sources)))
                for symbol, reason, sources in conn.execute(
                    "SELECT symbol, reason, sources FROM watchlist_entries ORDER BY seq"
                )
            )
        return Watchlist(entries=entries, refreshed_at=_from_iso(meta[0]))

    def save_watchlist(self, watchlist: Watchlist) -> None:
        with self._transaction() as conn:
            conn.execute("DELETE FROM watchlist_entries")
            conn.executemany(
                "INSERT INTO watchlist_entries (seq, symbol, reason, sources) VALUES (?, ?, ?, ?)",
                [
                    (seq, e.symbol, e.reason, json.dumps(list(e.sources)))
                    for seq, e in enumerate(watchlist.entries)
                ],
            )
            conn.execute(
                "INSERT OR REPLACE INTO watchlist_meta (id, refreshed_at) VALUES (1, ?)",
                (_to_iso(watchlist.refreshed_at),),
            )

    # --- plumbing ---

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """One connection per operation; commits on success, rolls back everything on error."""
        try:
            conn = sqlite3.connect(self._path)
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot open database at {self._path}") from exc
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                yield conn
        except sqlite3.Error as exc:
            raise StorageError(f"Database operation failed: {exc}") from exc
        finally:
            conn.close()


def _write_portfolio(conn: sqlite3.Connection, portfolio: Portfolio) -> None:
    conn.execute("INSERT OR REPLACE INTO portfolio (id, cash) VALUES (1, ?)", (str(portfolio.cash),))
    conn.execute("DELETE FROM positions")
    conn.executemany(
        "INSERT INTO positions (symbol, quantity, average_cost) VALUES (?, ?, ?)",
        [(p.symbol, p.quantity, str(p.average_cost)) for p in portfolio.positions.values()],
    )


def _write_run(conn: sqlite3.Connection, run: DecisionRun) -> None:
    conn.execute(
        """INSERT INTO runs (id, trigger, started_at, finished_at, status, failure_reason,
                             input_tokens, output_tokens, searches, trace_id, model, strategy_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.id,
            run.trigger.value,
            _to_iso(run.started_at),
            _to_iso(run.finished_at) if run.finished_at else None,
            run.status.value,
            run.failure_reason,
            run.cost.input_tokens,
            run.cost.output_tokens,
            run.cost.searches,
            run.trace_id,
            run.cost.model,
            run.strategy_version,
        ),
    )
    conn.executemany(
        """INSERT INTO findings (run_id, seq, symbol, summary, sources, warnings, price, change_percent)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                run.id,
                seq,
                f.symbol,
                f.summary,
                json.dumps(list(f.sources)),
                json.dumps(list(f.warnings)),
                _decimal_text(f.price),
                _decimal_text(f.change_percent),
            )
            for seq, f in enumerate(run.findings)
        ],
    )
    conn.executemany(
        """INSERT INTO order_results (run_id, seq, symbol, side, quantity, reason, status,
                                      price, fee, rejection_reason, strategy_section)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                run.id,
                seq,
                r.order.symbol,
                r.order.side.value,
                r.order.quantity,
                r.order.reason,
                r.status.value,
                _decimal_text(r.price),
                _decimal_text(r.fee),
                r.rejection_reason.name if r.rejection_reason else None,
                r.order.follows,
            )
            for seq, r in enumerate(run.order_results)
        ],
    )


def _read_run(conn: sqlite3.Connection, row: sqlite3.Row) -> DecisionRun:
    findings = tuple(
        Finding(
            f["symbol"],
            f["summary"],
            tuple(json.loads(f["sources"])),
            tuple(json.loads(f["warnings"])),
            _decimal_or_none(f["price"]),
            _decimal_or_none(f["change_percent"]),
        )
        for f in conn.execute("SELECT * FROM findings WHERE run_id = ? ORDER BY seq", (row["id"],))
    )
    order_results = tuple(
        OrderResult(
            order=Order(o["symbol"], Side(o["side"]), o["quantity"], o["reason"], o["strategy_section"]),
            status=OrderStatus(o["status"]),
            price=_decimal_or_none(o["price"]),
            fee=_decimal_or_none(o["fee"]),
            rejection_reason=RejectionReason[o["rejection_reason"]] if o["rejection_reason"] else None,
        )
        for o in conn.execute("SELECT * FROM order_results WHERE run_id = ? ORDER BY seq", (row["id"],))
    )
    return DecisionRun(
        id=row["id"],
        trigger=RunTrigger(row["trigger"]),
        started_at=_from_iso(row["started_at"]),
        finished_at=_from_iso(row["finished_at"]) if row["finished_at"] else None,
        status=RunStatus(row["status"]),
        failure_reason=row["failure_reason"],
        findings=findings,
        order_results=order_results,
        cost=RunCost(row["input_tokens"], row["output_tokens"], row["searches"], row["model"]),
        trace_id=row["trace_id"],
        strategy_version=row["strategy_version"],
    )


def _write_strategy_review(conn: sqlite3.Connection, review: StrategyReview) -> None:
    conn.execute(
        """INSERT INTO strategy_reviews (id, trigger, started_at, finished_at, status, failure_reason,
                                         reviewed_version, decision, reason, targets_verdict, targets_note,
                                         followed, followed_note, section_changes, scorecard,
                                         input_tokens, output_tokens, model, trace_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            review.id,
            review.trigger.value,
            _to_iso(review.started_at),
            _to_iso(review.finished_at) if review.finished_at else None,
            review.status.value,
            review.failure_reason,
            review.reviewed_version,
            review.decision.value if review.decision else None,
            review.reason,
            review.targets_verdict.value if review.targets_verdict else None,
            review.targets_note,
            review.followed.value if review.followed else None,
            review.followed_note,
            json.dumps({section.value: why for section, why in review.section_changes.items()}),
            json.dumps(_scorecard_to_json(review.scorecard)) if review.scorecard else None,
            review.cost.input_tokens,
            review.cost.output_tokens,
            review.cost.model,
            review.trace_id,
        ),
    )


def _read_strategy_review(row: sqlite3.Row) -> StrategyReview:
    return StrategyReview(
        id=row["id"],
        trigger=ReviewTrigger(row["trigger"]),
        started_at=_from_iso(row["started_at"]),
        finished_at=_from_iso(row["finished_at"]) if row["finished_at"] else None,
        status=RunStatus(row["status"]),
        failure_reason=row["failure_reason"],
        reviewed_version=row["reviewed_version"],
        decision=ReviewDecision(row["decision"]) if row["decision"] else None,
        reason=row["reason"],
        cost=RunCost(row["input_tokens"], row["output_tokens"], 0, row["model"]),
        trace_id=row["trace_id"],
        targets_verdict=TargetsVerdict(row["targets_verdict"]) if row["targets_verdict"] else None,
        targets_note=row["targets_note"],
        followed=Followed(row["followed"]) if row["followed"] else None,
        followed_note=row["followed_note"],
        section_changes={StrategySection(k): why for k, why in json.loads(row["section_changes"]).items()},
        scorecard=_scorecard_from_json(json.loads(row["scorecard"])) if row["scorecard"] else None,
    )


def _write_strategy_version(conn: sqlite3.Connection, version: StrategyVersion) -> None:
    conn.execute(
        """INSERT INTO strategy_versions (number, what_i_look_for, position_size, when_i_sell, cash_and_pace,
                                          targets, started_at, ended_at, review_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            version.number,
            *(text for _, text in version.strategy.sections()),
            _to_iso(version.started_at),
            _to_iso(version.ended_at) if version.ended_at else None,
            version.review_id,
        ),
    )


def _read_strategy_version(row: sqlite3.Row) -> StrategyVersion:
    return StrategyVersion(
        number=row["number"],
        strategy=Strategy(**{section.value: row[section.value] for section in StrategySection}),
        started_at=_from_iso(row["started_at"]),
        ended_at=_from_iso(row["ended_at"]) if row["ended_at"] else None,
        review_id=row["review_id"],
    )


def _scorecard_to_json(card: Scorecard) -> dict:
    return {
        "period_start": _to_iso(card.period_start),
        "period_end": _to_iso(card.period_end),
        "portfolio_percent": str(card.portfolio_percent),
        "benchmark_percent": str(card.benchmark_percent),
        "trading_runs": card.trading_runs,
        "trades": card.trades,
        "fees": str(card.fees),
        "closed_trades": [[t.symbol, str(t.gain)] for t in card.closed_trades],
        "holdings": [[h.symbol, str(h.gain_percent)] for h in card.holdings],
        "average_cash_percent": str(card.average_cash_percent),
        "followed_orders": card.followed_orders,
        "deviations": card.deviations,
        "order_outcomes": [
            {
                "at": _to_iso(o.at),
                "side": o.side.value,
                "quantity": o.quantity,
                "symbol": o.symbol,
                "price": str(o.price),
                "price_now": _optional_text(o.price_now),
                "trading_days": o.trading_days,
                "benchmark_percent": _optional_text(o.benchmark_percent),
            }
            for o in card.order_outcomes
        ],
        "unbought": [[m.symbol, _optional_text(m.percent)] for m in card.unbought],
        "days": [
            {
                "day": d.day.isoformat(),
                "runs": d.runs,
                "buys": d.buys,
                "sells": d.sells,
                "rejected": d.rejected,
                "held": d.held,
                "last_summary": d.last_summary,
            }
            for d in card.days
        ],
    }


def _scorecard_from_json(data: dict) -> Scorecard:
    return Scorecard(
        period_start=_from_iso(data["period_start"]),
        period_end=_from_iso(data["period_end"]),
        portfolio_percent=Decimal(data["portfolio_percent"]),
        benchmark_percent=Decimal(data["benchmark_percent"]),
        trading_runs=data["trading_runs"],
        trades=data["trades"],
        fees=Decimal(data["fees"]),
        closed_trades=tuple(ClosedTrade(symbol, Decimal(gain)) for symbol, gain in data["closed_trades"]),
        holdings=tuple(HoldingResult(symbol, Decimal(gain)) for symbol, gain in data["holdings"]),
        average_cash_percent=Decimal(data["average_cash_percent"]),
        followed_orders=data["followed_orders"],
        deviations=data["deviations"],
        # Scorecards saved before these were added have none.
        order_outcomes=tuple(
            OrderOutcome(
                at=_from_iso(o["at"]),
                side=Side(o["side"]),
                quantity=o["quantity"],
                symbol=o["symbol"],
                price=Decimal(o["price"]),
                price_now=_optional_decimal(o["price_now"]),
                trading_days=o["trading_days"],
                benchmark_percent=_optional_decimal(o["benchmark_percent"]),
            )
            for o in data.get("order_outcomes", [])
        ),
        unbought=tuple(StockMove(symbol, _optional_decimal(percent)) for symbol, percent in data.get("unbought", [])),
        days=tuple(
            TradingDay(**{**d, "day": date.fromisoformat(d["day"])}) for d in data.get("days", [])
        ),
    )


def _optional_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _optional_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _date_text(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _date_or_none(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _decimal_or_none(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None
