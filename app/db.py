import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
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
                servicios_aux REAL NOT NULL DEFAULT 0,
                perdidas REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL,
                source_id TEXT NOT NULL DEFAULT 'balance-xlsx',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (year, month, source_id)
            )
            """
        )
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(balance_monthly)").fetchall()}
        if "servicios_aux" not in existing_cols:
            conn.execute("ALTER TABLE balance_monthly ADD COLUMN servicios_aux REAL NOT NULL DEFAULT 0")
        if "perdidas" not in existing_cols:
            conn.execute("ALTER TABLE balance_monthly ADD COLUMN perdidas REAL NOT NULL DEFAULT 0")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS balance_metadata (
                year INTEGER NOT NULL,
                source_id TEXT NOT NULL,
                observed_months TEXT NOT NULL,
                last_month TEXT,
                month_count INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (year, source_id)
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


def save_balance_rows(
    year: int,
    source_id: str,
    months: List[str],
    regulados: List[float],
    libres: List[float],
    coes: List[float],
    servicios_aux: List[float],
    perdidas: List[float],
    observed_months: List[str] | None = None,
) -> None:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        for idx, month in enumerate(months):
            conn.execute(
                """
                INSERT OR REPLACE INTO balance_monthly (year, month, regulados, libres, coes, servicios_aux, perdidas, total, source_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    year,
                    month,
                    regulados[idx],
                    libres[idx],
                    coes[idx],
                    servicios_aux[idx],
                    perdidas[idx],
                    regulados[idx] + libres[idx] + coes[idx],
                    source_id,
                    now,
                ),
            )
        observed = observed_months or months
        conn.execute(
            """
            INSERT OR REPLACE INTO balance_metadata (year, source_id, observed_months, last_month, month_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                year,
                source_id,
                json.dumps(observed),
                observed[-1] if observed else None,
                len(observed),
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
        meta_params = params.copy()
        metadata = conn.execute(
            "SELECT observed_months, last_month, month_count FROM balance_metadata WHERE year = ?" + (" AND source_id = ?" if source_id else ""),
            meta_params,
        ).fetchone()

    ordered = {m: {"regulados": 0.0, "libres": 0.0, "coes": 0.0, "servicios_aux": 0.0, "perdidas": 0.0, "total": 0.0} for m in MONTH_ORDER}
    for row in rows:
        if row["month"] not in ordered:
            continue
        ordered[row["month"]] = {
            "regulados": float(row["regulados"]),
            "libres": float(row["libres"]),
            "coes": float(row["coes"]),
            "servicios_aux": float(row["servicios_aux"]) if "servicios_aux" in row.keys() else 0.0,
            "perdidas": float(row["perdidas"]) if "perdidas" in row.keys() else 0.0,
            "total": float(row["total"]),
        }

    observed_months = MONTH_ORDER
    last_month = MONTH_ORDER[-1]
    if metadata:
        observed_months = json.loads(metadata["observed_months"]) if metadata["observed_months"] else MONTH_ORDER
        last_month = metadata["last_month"] or (observed_months[-1] if observed_months else None)
    observed_months = [m for m in observed_months if m in MONTH_ORDER]
    month_count = len(observed_months)

    return {
        "year": year,
        "months": MONTH_ORDER,
        "observed_months": observed_months,
        "month_count": month_count,
        "last_month": last_month,
        "regulados": [ordered[m]["regulados"] for m in MONTH_ORDER],
        "libres": [ordered[m]["libres"] for m in MONTH_ORDER],
        "coes": [ordered[m]["coes"] for m in MONTH_ORDER],
        "servicios_aux": [ordered[m]["servicios_aux"] for m in MONTH_ORDER],
        "perdidas": [ordered[m]["perdidas"] for m in MONTH_ORDER],
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
