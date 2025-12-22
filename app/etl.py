import asyncio
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd
from openpyxl import load_workbook
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import DATA_DIR, DEFAULT_SOURCE_ID, MONTH_ORDER, WATCH_DEBOUNCE_SECONDS, XLSX_RETRY_COUNT, XLSX_RETRY_DELAY
from .db import record_etl_run, save_balance_rows, upsert_source

logger = logging.getLogger(__name__)


MONTH_ALIASES: Dict[str, str] = {
    "ene": "Ene",
    "enero": "Ene",
    "feb": "Feb",
    "febrero": "Feb",
    "mar": "Mar",
    "marzo": "Mar",
    "abr": "Abr",
    "abril": "Abr",
    "may": "May",
    "mayo": "May",
    "jun": "Jun",
    "junio": "Jun",
    "jul": "Jul",
    "julio": "Jul",
    "ago": "Ago",
    "agosto": "Ago",
    "set": "Set",
    "sep": "Set",
    "sept": "Set",
    "septiembre": "Set",
    "oct": "Oct",
    "octubre": "Oct",
    "nov": "Nov",
    "noviembre": "Nov",
    "dic": "Dic",
    "diciembre": "Dic",
}


@dataclass
class BalanceParseResult:
    year: int
    months: List[str]
    regulados: List[float]
    libres: List[float]
    coes: List[float]
    servicios_aux: List[float]
    perdidas: List[float]
    observed_months: List[str]
    warnings: List[str]
    source_id: str


def normalize_text(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )


def parse_number(raw: object) -> float:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace("\u00a0", "").replace(" ", "")
    if text == "":
        return 0.0
    # Remove any non-digit separators except comma and dot
    text = re.sub(r"[^0-9,.-]", "", text)
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    elif text.count(".") > 1 and text.count(",") == 0:
        text = text.replace(".", "")
    elif text.count(".") == 1 and text.count(",") == 1:
        if text.rfind(".") < text.rfind(","):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        logger.warning("Could not parse number from '%s'", raw)
        return 0.0


def _find_title_year(sheet) -> Optional[int]:
    regex = re.compile(r"balance de energ[ií]a en mwh\s*-\s*a[ñn]o\s*(\d{4})", re.IGNORECASE)
    for row in sheet.iter_rows(values_only=True):
        for cell in row:
            if isinstance(cell, str):
                match = regex.search(cell)
                if match:
                    return int(match.group(1))
    return None


def _canonical_header(value: object) -> str:
    if value is None:
        return ""
    norm = normalize_text(str(value))
    if "descripcion" in norm:
        return "descripcion"
    if "acumulado" in norm:
        return "acumulado"
    for alias, canonical in MONTH_ALIASES.items():
        if norm.startswith(alias):
            return canonical
    return norm


def _parse_balance_sheet(sheet, year: int, source_id: str) -> BalanceParseResult:
    df = pd.DataFrame(sheet.values)
    header_idx = None
    for idx, row in df.iterrows():
        normalized = [_canonical_header(v) for v in row.tolist()]
        if "descripcion" in normalized and "acumulado" in normalized:
            month_hits = sum(val in MONTH_ALIASES.values() for val in normalized)
            if month_hits >= 3:
                header_idx = idx
                break

    if header_idx is None:
        raise ValueError("No se encontró fila de encabezados con 'DESCRIPCIÓN' y meses.")

    raw_headers = [_canonical_header(v) for v in df.iloc[header_idx].tolist()]
    df.columns = raw_headers
    data = df.iloc[header_idx + 1 :].copy()
    data = data.dropna(how="all")

    month_columns = [c for c in raw_headers if c in MONTH_ALIASES.values()]
    if not month_columns:
        raise ValueError("No se encontraron columnas de meses.")

    target_rows = {
        "regulados": ["a emp. distribuidoras", "distribuidoras"],
        "libres": ["a clientes libres", "clientes libres"],
        "coes": ["coes"],
        "servicios_aux": ["consumo propio de centrales", "servicios auxiliares"],
        "perdidas": ["perdidas sistemas transmision", "perdidas", "perdidas sistemas transmisión"],
    }

    series: Dict[str, List[float]] = {k: [] for k in target_rows}
    warnings: List[str] = []
    month_presence = [False for _ in month_columns]

    for metric, patterns in target_rows.items():
        values_by_month = []
        matched_row = None
        for _, row in data.iterrows():
            desc = normalize_text(str(row.get("descripcion", "")))
            if any(pat in desc for pat in patterns):
                matched_row = row
                break

        if matched_row is None:
            warnings.append(f"No se encontró fila para '{metric}'.")
            values_by_month = [0.0 for _ in month_columns]
        else:
            for midx, col in enumerate(month_columns):
                raw_value = matched_row.get(col)
                parsed = parse_number(raw_value)
                values_by_month.append(parsed)
                if raw_value not in (None, "", "-") and not (isinstance(raw_value, float) and pd.isna(raw_value)):
                    month_presence[midx] = month_presence[midx] or parsed != 0
        series[metric] = values_by_month

    # align months to standard order
    aligned_months: List[str] = []
    aligned: Dict[str, List[float]] = {k: [] for k in target_rows}
    observed_months: List[str] = []
    last_with_data = -1
    for midx, present in enumerate(month_presence):
        if present or any(series[m][midx] != 0 for m in target_rows):
            last_with_data = midx

    active_month_columns = month_columns if last_with_data < 0 else month_columns[: last_with_data + 1]

    for target_month in MONTH_ORDER:
        if target_month in active_month_columns:
            idx = active_month_columns.index(target_month)
            aligned_months.append(target_month)
            observed_months.append(target_month)
            for metric in target_rows:
                aligned[metric].append(series[metric][idx])
        else:
            warnings.append(f"Mes '{target_month}' no encontrado en el archivo. Se usa 0.")
            aligned_months.append(target_month)
            for metric in target_rows:
                aligned[metric].append(0.0)

    return BalanceParseResult(
        year=year,
        months=aligned_months,
        regulados=aligned["regulados"],
        libres=aligned["libres"],
        coes=aligned["coes"],
        servicios_aux=aligned["servicios_aux"],
        perdidas=aligned["perdidas"],
        observed_months=observed_months,
        warnings=warnings,
        source_id=source_id,
    )


def parse_balance_workbook(path: Path, source_id: str = DEFAULT_SOURCE_ID) -> List[BalanceParseResult]:
    workbook = load_workbook(path, data_only=True)
    results: List[BalanceParseResult] = []
    for sheet in workbook.worksheets:
        year = _find_title_year(sheet)
        if not year:
            continue
        try:
            results.append(_parse_balance_sheet(sheet, year, source_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo parsear hoja %s (%s): %s", sheet.title, path, exc)
    if not results:
        raise ValueError("No se encontró un título 'BALANCE DE ENERGÍA EN MWh - AÑO YYYY' en el Excel.")
    return results


def process_balance_file(path: Path, dispatch_event: Callable[[dict], None], source_id: str = DEFAULT_SOURCE_ID) -> None:
    logger.info("Procesando archivo %s", path)
    warnings: List[str] = []
    try:
        results = parse_with_retries(path, source_id=source_id)
        run_warnings: List[str] = []
        first_result = results[0]
        for result in results:
            warnings = result.warnings
            save_balance_rows(
                result.year,
                result.source_id,
                result.months,
                result.regulados,
                result.libres,
                result.coes,
                result.servicios_aux,
                result.perdidas,
                observed_months=result.observed_months,
            )
            run_warnings.extend([f"{result.year}: {w}" for w in warnings])
            dispatch_event(
                {
                    "type": "DATASET_UPDATED",
                    "dataset_id": "balance",
                    "source_id": result.source_id,
                    "year": result.year,
                    "message": f"Balance actualizado para {result.year}",
                    "warnings": warnings,
                }
            )
        upsert_source(first_result.source_id, "balance", path.name, last_ingested=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        record_etl_run(first_result.source_id, "balance", "SUCCESS", f"Ingestado {len(results)} hojas", run_warnings)
        if run_warnings:
            logger.warning("ETL finalizó con advertencias: %s", run_warnings)
    except FileNotFoundError:
        msg = f"Archivo {path} no encontrado. Se omite."
        logger.warning(msg)
        warnings.append(msg)
        record_etl_run(source_id, "balance", "WARNING", msg, warnings)
    except Exception as exc:  # noqa: BLE001
        msg = f"Error procesando {path}: {exc}"
        logger.exception(msg)
        warnings.append(msg)
        record_etl_run(source_id, "balance", "ERROR", msg, warnings)
        dispatch_event(
            {
                "type": "ETL_ERROR",
                "dataset_id": "balance",
                "source_id": source_id,
                "message": msg,
                "warnings": warnings,
            }
        )


def parse_with_retries(path: Path, source_id: str = DEFAULT_SOURCE_ID) -> List[BalanceParseResult]:
    last_exc: Exception | None = None
    for attempt in range(1, XLSX_RETRY_COUNT + 1):
        try:
            return parse_balance_workbook(path, source_id)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= XLSX_RETRY_COUNT:
                break
            logger.warning("Intento %s/%s fallido (%s). Reintentando en %.1fs...", attempt, XLSX_RETRY_COUNT, exc, XLSX_RETRY_DELAY)
            time.sleep(XLSX_RETRY_DELAY)
    raise last_exc or RuntimeError("Fallo al parsear Excel.")


class ExcelEventHandler(FileSystemEventHandler):
    def __init__(self, dispatch_event: Callable[[dict], None], source_id: str = DEFAULT_SOURCE_ID):
        super().__init__()
        self._timers: Dict[Path, threading.Timer] = {}
        self.dispatch_event = dispatch_event
        self.source_id = source_id

    def _schedule(self, path: Path) -> None:
        if path.name.startswith("~$") or path.suffix.lower() not in {".xlsx", ".xlsm"}:
            return
        if path in self._timers:
            self._timers[path].cancel()
        timer = threading.Timer(WATCH_DEBOUNCE_SECONDS, self._run_etl, args=[path])
        self._timers[path] = timer
        timer.start()

    def _run_etl(self, path: Path) -> None:
        try:
            process_balance_file(path, self.dispatch_event, source_id=self.source_id)
        finally:
            self._timers.pop(path, None)

    def on_created(self, event):
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule(Path(event.src_path))


def start_watcher(dispatch_event: Callable[[dict], None], source_id: str = DEFAULT_SOURCE_ID) -> Observer:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handler = ExcelEventHandler(dispatch_event, source_id=source_id)
    observer = Observer()
    observer.schedule(handler, str(DATA_DIR), recursive=False)
    observer.daemon = True
    observer.start()
    logger.info("Watchdog iniciado en %s", DATA_DIR)
    return observer
