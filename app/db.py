import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .config import DB_PATH, DATA_DIR, MONTH_ORDER

logger = logging.getLogger(__name__)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Using database at %s", DB_PATH)
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS balance_monthly (
                year INTEGER NOT NULL,
                month TEXT NOT NULL,
                regulados REAL NOT NULL,
                libres REAL NOT NULL,
                coes REAL NOT NULL,
                total REAL NOT NULL,
                source_id TEXT NOT NULL DEFAULT 'balance-xlsx',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (year, month, source_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                file_name TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_ingested TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS etl_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT,
                dataset_id TEXT,
                status TEXT,
                message TEXT,
                warnings TEXT,
                ran_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def upsert_source(source_id: str, dataset_id: str, file_name: str | None, last_ingested: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sources (source_id, dataset_id, file_name, enabled, last_ingested, created_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                dataset_id=excluded.dataset_id,
                file_name=excluded.file_name,
                last_ingested=excluded.last_ingested
            """,
            (source_id, dataset_id, file_name, last_ingested, now),
        )
        conn.commit()


def save_balance_rows(year: int, source_id: str, months: List[str], regulados: List[float], libres: List[float], coes: List[float]) -> None:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        for idx, month in enumerate(months):
            conn.execute(
                """
                INSERT OR REPLACE INTO balance_monthly (year, month, regulados, libres, coes, total, source_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    year,
                    month,
                    regulados[idx],
                    libres[idx],
                    coes[idx],
                    regulados[idx] + libres[idx] + coes[idx],
                    source_id,
                    now,
                ),
            )
        conn.commit()


def record_etl_run(source_id: str, dataset_id: str, status: str, message: str, warnings: Iterable[str]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO etl_runs (source_id, dataset_id, status, message, warnings, ran_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_id, dataset_id, status, message, "; ".join(warnings), datetime.utcnow().isoformat()),
        )
        conn.commit()


def list_balance_years() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT year FROM balance_monthly ORDER BY year").fetchall()
        return [int(r["year"]) for r in rows]


def fetch_balance_year(year: int, source_id: str | None = None) -> dict:
    params: list = [year]
    query = "SELECT * FROM balance_monthly WHERE year = ?"
    if source_id:
        query += " AND source_id = ?"
        params.append(source_id)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    ordered = {m: {"regulados": 0.0, "libres": 0.0, "coes": 0.0, "total": 0.0} for m in MONTH_ORDER}
    for row in rows:
        if row["month"] not in ordered:
            continue
        ordered[row["month"]] = {
            "regulados": float(row["regulados"]),
            "libres": float(row["libres"]),
            "coes": float(row["coes"]),
            "total": float(row["total"]),
        }

    return {
        "year": year,
        "months": MONTH_ORDER,
        "regulados": [ordered[m]["regulados"] for m in MONTH_ORDER],
        "libres": [ordered[m]["libres"] for m in MONTH_ORDER],
        "coes": [ordered[m]["coes"] for m in MONTH_ORDER],
        "total": [ordered[m]["total"] for m in MONTH_ORDER],
    }


def list_sources() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT source_id, dataset_id, file_name, enabled, last_ingested FROM sources ORDER BY source_id"
        ).fetchall()
        return [
            {
                "source_id": r["source_id"],
                "dataset_id": r["dataset_id"],
                "file_name": r["file_name"],
                "enabled": bool(r["enabled"]),
                "last_ingested": r["last_ingested"],
            }
            for r in rows
        ]
