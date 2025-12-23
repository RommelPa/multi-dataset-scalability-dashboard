import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
from openpyxl.workbook.workbook import Workbook

from .config import MONTH_ORDER, DEFAULT_SOURCE_ID

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
class BalanceEnergySeries:
    regulados: List[float]
    libres: List[float]
    coes: List[float]
    servicios_aux: List[float]
    perdidas: List[float]


@dataclass
class BalanceSalesSeries:
    regulados: List[float]
    libres: List[float]
    coes_spot: List[float]
    otros: List[float]


@dataclass
class BalanceParseResult:
    year: int
    months: List[str]
    observed_months: List[str]
    energy: BalanceEnergySeries
    sales: Optional[BalanceSalesSeries]
    warnings: List[str]
    source_id: str
    sheet_name: str
    last_month: Optional[str]


@dataclass
class _SheetCandidate:
    year: int
    sheet_name: str
    version_priority: int
    revision_number: int
    sheet: object


_VERSION_PRIORITY = {"R2": 5, "R1": 4, "V1": 3, "REV": 2, "BASE": 1}

_TARGET_ROWS_ENERGY: Dict[str, List[str]] = {
    "regulados": ["A EMP. DISTRIBUIDORAS", "A EMP DISTRIBUIDORAS", "MERCADO REGULADO", "REGULADOS"],
    "libres": ["A CLIENTES LIBRES", "MERCADO LIBRE", "LIBRES"],
    "coes": ["COES", "SPOT", "COES SPOT", "COES-SPOT", "MERCADO SPOT"],
    "servicios_aux": ["SERVICIOS AUXILIARES", "CONSUMO PROPIO DE CENTRALES", "SSAA"],
    "perdidas": ["PERDIDAS SISTEMAS TRANSMISION", "PERDIDAS SISTEMAS TRANSMISION", "PERDIDAS"],
}

_TARGET_ROWS_SALES: Dict[str, List[str]] = {
    "regulados": ["REGULADOS", "MERCADO REGULADO", "A EMP. DISTRIBUIDORAS"],
    "libres": ["LIBRES", "MERCADO LIBRE", "A CLIENTES LIBRES"],
    "coes_spot": ["COES", "SPOT", "COES-SPOT", "COES SPOT"],
    "otros": ["OTROS"],
}


def normalize_label(value: object) -> str:
    """Uppercase, remove accents, collapse spaces, strip trailing colon/hyphen variants."""
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper().strip()
    text = text.replace("–", "-").replace("—", "-")
    text = text.rstrip(":")
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_number(raw: object) -> float:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace("\u00a0", "")
    if text == "":
        return 0.0
    text = text.replace(" ", "")
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


def _canonical_header(value: object) -> str:
    if value is None:
        return ""
    norm = normalize_label(value)
    if norm.startswith("DESCRIPCION"):
        return "descripcion"
    if norm.startswith("ACUMULADO"):
        return "acumulado"
    for alias, canonical in MONTH_ALIASES.items():
        if norm.lower().startswith(alias):
            return canonical
    return norm


def _find_title_year(sheet) -> Optional[int]:
    regex = re.compile(r"BALANCE\s+DE\s+ENERG[ÍI]A\s+EN\s+MWH\s*-\s*A[ÑN]O\s*(\d{4})", re.IGNORECASE)
    for row in sheet.iter_rows(values_only=True):
        for cell in row:
            if isinstance(cell, str):
                match = regex.search(cell)
                if match:
                    return int(match.group(1))
    return None


def _score_version(sheet_name: str) -> tuple[int, int, str]:
    compact = re.sub(r"\s+", "", sheet_name.upper())
    compact = compact.replace("(", "").replace(")", "")
    revision_number = 0
    if "R2" in compact:
        return _VERSION_PRIORITY["R2"], revision_number, "R2"
    if "R1" in compact:
        return _VERSION_PRIORITY["R1"], revision_number, "R1"
    if "V1" in compact:
        return _VERSION_PRIORITY["V1"], revision_number, "V1"
    rev_match = re.search(r"REV(?:ISION)?(\d+)?", compact)
    if rev_match:
        revision_number = int(rev_match.group(1) or 0)
        return _VERSION_PRIORITY["REV"], revision_number, f"REV{revision_number or ''}"
    return _VERSION_PRIORITY["BASE"], revision_number, "BASE"


def _match_row(targets: List[str], candidate: str) -> bool:
    for target in targets:
        if target in candidate:
            return True
    return False


class BalanceTransformer:
    def __init__(self, workbook: Workbook, source_id: str = DEFAULT_SOURCE_ID):
        self.workbook = workbook
        self.source_id = source_id

    def transform(self) -> List[BalanceParseResult]:
        candidates = self._select_candidates()
        results: List[BalanceParseResult] = []
        for year, candidate in candidates.items():
            parsed = self._parse_sheet(candidate.sheet, year, candidate.sheet_name)
            results.append(parsed)
        if not results:
            raise ValueError("No se encontró un título 'BALANCE DE ENERGÍA EN MWh - AÑO YYYY' en el Excel.")
        results.sort(key=lambda r: r.year)
        return results

    def _select_candidates(self) -> Dict[int, _SheetCandidate]:
        selected: Dict[int, _SheetCandidate] = {}
        for sheet in self.workbook.worksheets:
            year = _find_title_year(sheet)
            if not year:
                continue
            version_priority, revision_number, label = _score_version(sheet.title)
            candidate = _SheetCandidate(
                year=year,
                sheet_name=sheet.title,
                version_priority=version_priority,
                revision_number=revision_number,
                sheet=sheet,
            )
            existing = selected.get(year)
            if existing is None or self._is_better(candidate, existing):
                selected[year] = candidate
                logger.info("Seleccionando hoja %s para año %s (versión %s)", sheet.title, year, label)
            else:
                logger.info("Se descarta hoja %s para año %s (existe versión más nueva)", sheet.title, year)
        return selected

    @staticmethod
    def _is_better(candidate: _SheetCandidate, current: _SheetCandidate) -> bool:
        if candidate.version_priority != current.version_priority:
            return candidate.version_priority > current.version_priority
        return candidate.revision_number >= current.revision_number

    def _parse_sheet(self, sheet, year: int, sheet_name: str) -> BalanceParseResult:
        df = pd.DataFrame(sheet.values)
        header_indices: List[int] = []
        for idx, row in df.iterrows():
            normalized = [_canonical_header(v) for v in row.tolist()]
            month_hits = sum(val in MONTH_ALIASES.values() for val in normalized)
            if "descripcion" in normalized and month_hits >= 3:
                header_indices.append(idx)

        if not header_indices:
            raise ValueError("No se encontró fila de encabezados con 'DESCRIPCIÓN' y meses.")

        energy_series: Optional[BalanceEnergySeries] = None
        sales_series: Optional[BalanceSalesSeries] = None
        warnings: List[str] = []
        observed_months: List[str] = []
        last_month: Optional[str] = None
        energy_months: List[str] = MONTH_ORDER

        for header_idx in header_indices:
            context_text = " ".join(
                normalize_label(cell)
                for cell in df.iloc[max(0, header_idx - 3) : header_idx].stack()
                if isinstance(cell, str)
            )
            is_sales = any(keyword in context_text for keyword in ["MILLONES", "SOLES", "S/", "MONETARI"])
            try:
                months, month_presence, parsed_series, table_warnings = self._extract_table(df, header_idx, is_sales=is_sales)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo parsear tabla en fila %s de %s: %s", header_idx, sheet_name, exc)
                continue
            warnings.extend(table_warnings)

            if is_sales and sales_series is None:
                sales_series = BalanceSalesSeries(
                    regulados=parsed_series.get("regulados", [0.0 for _ in months]),
                    libres=parsed_series.get("libres", [0.0 for _ in months]),
                    coes_spot=parsed_series.get("coes_spot", [0.0 for _ in months]),
                    otros=parsed_series.get("otros", [0.0 for _ in months]),
                )
            elif not is_sales and energy_series is None:
                energy_series = BalanceEnergySeries(
                    regulados=parsed_series.get("regulados", [0.0 for _ in months]),
                    libres=parsed_series.get("libres", [0.0 for _ in months]),
                    coes=parsed_series.get("coes", [0.0 for _ in months]),
                    servicios_aux=parsed_series.get("servicios_aux", [0.0 for _ in months]),
                    perdidas=parsed_series.get("perdidas", [0.0 for _ in months]),
                )
                energy_months = months
                observed_months = [month for month, present in zip(months, month_presence) if present]
                if observed_months:
                    last_month = observed_months[-1]
            elif is_sales and sales_series is not None:
                logger.info("Tabla de ventas duplicada en %s, se omite duplicado", sheet_name)
            elif not is_sales and energy_series is not None:
                logger.info("Tabla de energía duplicada en %s, se omite duplicado", sheet_name)

        if energy_series is None:
            raise ValueError(f"No se encontró tabla de energía para el año {year} en la hoja {sheet_name}")

        if not observed_months:
            observed_months = [m for m in MONTH_ORDER if m in energy_months]
            if observed_months:
                last_month = observed_months[-1]

        missing_rows = self._missing_rows_report(energy_series)
        warnings.extend(missing_rows)

        return BalanceParseResult(
            year=year,
            months=MONTH_ORDER,
            observed_months=observed_months or MONTH_ORDER,
            energy=energy_series,
            sales=sales_series,
            warnings=warnings,
            source_id=self.source_id,
            sheet_name=sheet_name,
            last_month=last_month,
        )

    def _extract_table(self, df: pd.DataFrame, header_idx: int, is_sales: bool) -> tuple[list[str], list[bool], Dict[str, List[float]], List[str]]:
        raw_headers = [_canonical_header(v) for v in df.iloc[header_idx].tolist()]
        data = df.iloc[header_idx + 1 :].copy().dropna(how="all")
        month_columns = [c for c in raw_headers if c in MONTH_ALIASES.values()]
        if not month_columns:
            raise ValueError("No se encontraron columnas de meses.")

        targets = _TARGET_ROWS_SALES if is_sales else _TARGET_ROWS_ENERGY
        series: Dict[str, List[float]] = {k: [] for k in targets}
        warnings: List[str] = []
        month_presence = [False for _ in month_columns]

        for metric, patterns in targets.items():
            values_by_month: List[float] = []
            matched_row = None
            for _, row in data.iterrows():
                desc = normalize_label(row.get("descripcion", ""))
                if _match_row(patterns, desc):
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

        aligned_months: List[str] = []
        aligned: Dict[str, List[float]] = {k: [] for k in targets}
        last_with_data = -1
        for midx, present in enumerate(month_presence):
            if present or any(series[m][midx] != 0 for m in targets):
                last_with_data = midx

        active_month_columns = month_columns if last_with_data < 0 else month_columns[: last_with_data + 1]

        for target_month in MONTH_ORDER:
            if target_month in active_month_columns:
                idx = active_month_columns.index(target_month)
                aligned_months.append(target_month)
                for metric in targets:
                    aligned[metric].append(series[metric][idx])
            else:
                warnings.append(f"Mes '{target_month}' no encontrado en la tabla. Se usa 0.")
                aligned_months.append(target_month)
                for metric in targets:
                    aligned[metric].append(0.0)

        if warnings:
            logger.warning("Advertencias al parsear tabla %s: %s", "ventas" if is_sales else "energía", warnings)
        if len(month_presence) < len(aligned_months):
            month_presence = month_presence + [False for _ in range(len(aligned_months) - len(month_presence))]
        return aligned_months, month_presence, aligned, warnings

    @staticmethod
    def _missing_rows_report(energy_series: BalanceEnergySeries) -> List[str]:
        warnings = []
        if not any(energy_series.regulados):
            warnings.append("No se encontró fila para 'A emp. Distribuidoras'")
        if not any(energy_series.libres):
            warnings.append("No se encontró fila para 'A clientes Libres'")
        if not any(energy_series.coes):
            warnings.append("No se encontró fila para 'COES'")
        if not any(energy_series.perdidas):
            warnings.append("No se encontró fila para 'Pérdidas'")
        if not any(energy_series.servicios_aux):
            warnings.append("No se encontró fila para 'Servicios auxiliares'")
        return warnings
