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
    version_priority: float
    revision_number: int
    sheet: object

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
    """Uppercase, remove accents, collapse spaces and punctuation for robust comparisons."""
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper().strip()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[;.:]", " ", text)
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


YEAR_REGEX = re.compile(r"\b(19|20)\d{2}\b")


def _extract_year_from_title(sheet_name: str) -> Optional[int]:
    spaced = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", sheet_name)
    spaced = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", spaced)
    match = YEAR_REGEX.search(spaced)
    if match:
        return int(match.group(0))
    return None


def _find_title_year(sheet) -> Optional[int]:
    regex = re.compile(r"BALANCE\s+DE\s+ENERG[ÍI]A\s+EN\s+MWH.*?(19|20)\d{2}", re.IGNORECASE)
    for row in sheet.iter_rows(values_only=True):
        for cell in row:
            if isinstance(cell, str):
                match = regex.search(cell)
                if match:
                    year_match = YEAR_REGEX.search(match.group(0))
                    if year_match:
                        return int(year_match.group(0))
    return None


def _score_version(sheet_name: str) -> tuple[float, int, str]:
    norm = normalize_label(sheet_name)
    revision_number = 0

    if re.search(r"R\s*-?\s*2\b", norm) or re.search(r"\(R\s*-?\s*2\)", sheet_name, re.IGNORECASE):
        return 4.0, revision_number, "R2"
    if re.search(r"R\s*-?\s*1\b", norm) or re.search(r"\(R\s*-?\s*1\)", sheet_name, re.IGNORECASE):
        return 3.0, revision_number, "R1"
    if re.search(r"V\s*-?\s*1\b", norm) or "V1" in norm:
        return 2.0, revision_number, "V1"

    rev_matches = [m for m in re.finditer(r"REV\s*-?\s*(\d+)?", norm)]
    if rev_matches:
        revision_number = max(int(m.group(1) or 0) for m in rev_matches)
        return 1.0 + revision_number / 1000.0, revision_number, f"REV{revision_number or ''}"

    return 0.0, revision_number, "BASE"


def _match_row(targets: List[str], candidate: str) -> bool:
    for target in targets:
        if target in candidate:
            return True
    return False


def _detect_section(label: str) -> Optional[str]:
    if not label:
        return None
    if "VENTA DE ENERGIA" in label or label.startswith("VENTA ENERGIA") or label.startswith("VENTA DE ENER"):
        return "venta"
    if "COMPRA DE ENERGIA" in label or label.startswith("COMPRA ENER") or label.startswith("COMPRA DE ENER"):
        return "compra"
    return None


def _is_blank_row(row: List[object]) -> bool:
    return all(
        cell is None or (isinstance(cell, float) and pd.isna(cell)) or (isinstance(cell, str) and cell.strip() == "")
        for cell in row
    )


def _locate_title_row(df: pd.DataFrame, expected_year: int) -> Optional[int]:
    regex = re.compile(r"BALANCE\s+DE\s+ENERG[ÍI]A\s+EN\s+MWH.*?(19|20)\d{2}", re.IGNORECASE)
    title_idx: Optional[int] = None
    for idx, row in df.iterrows():
        for cell in row.tolist():
            if isinstance(cell, str) and regex.search(cell):
                year_match = YEAR_REGEX.search(cell)
                if year_match and int(year_match.group(0)) == expected_year:
                    return idx
                if title_idx is None:
                    title_idx = idx
    return title_idx


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
            year = _extract_year_from_title(sheet.title)
            if not year:
                logger.info("Se ignora hoja %s (sin año detectable en el nombre)", sheet.title)
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
        title_row_idx = _locate_title_row(df, year)
        for idx, row in df.iterrows():
            normalized = [_canonical_header(v) for v in row.tolist()]
            month_hits = sum(val in MONTH_ALIASES.values() for val in normalized)
            if "descripcion" in normalized and month_hits >= 3:
                header_indices.append(idx)

        if not header_indices:
            raise ValueError("No se encontró fila de encabezados con 'DESCRIPCIÓN' y meses.")

        if title_row_idx is not None:
            header_indices = [idx for idx in header_indices if idx > title_row_idx] or header_indices

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
        desc_col_idx = next((idx for idx, val in enumerate(raw_headers) if val == "descripcion"), 0)
        month_columns = [(idx, val) for idx, val in enumerate(raw_headers) if val in MONTH_ALIASES.values()]
        if not month_columns:
            raise ValueError("No se encontraron columnas de meses.")

        data_rows: List[tuple[str, List[float], List[object]]] = []
        month_presence = [False for _ in month_columns]
        for ridx in range(header_idx + 1, len(df)):
            row_list = df.iloc[ridx].tolist()
            if _is_blank_row(row_list):
                break
            desc_raw = row_list[desc_col_idx] if desc_col_idx < len(row_list) else ""
            desc_norm = normalize_label(desc_raw)
            values: List[float] = []
            for midx, (col_idx, _) in enumerate(month_columns):
                raw_value = row_list[col_idx] if col_idx < len(row_list) else None
                parsed = parse_number(raw_value)
                values.append(parsed)
                if raw_value not in (None, "", "-") and not (isinstance(raw_value, float) and pd.isna(raw_value)):
                    month_presence[midx] = month_presence[midx] or parsed != 0
            data_rows.append((desc_norm, values, row_list))

        targets = _TARGET_ROWS_SALES if is_sales else _TARGET_ROWS_ENERGY
        series: Dict[str, List[float]] = {k: [0.0 for _ in month_columns] for k in targets}
        warnings: List[str] = []

        if is_sales:
            for metric, patterns in targets.items():
                matched = next((row for row in data_rows if _match_row(patterns, row[0])), None)
                if matched:
                    series[metric] = matched[1]
                else:
                    warnings.append(f"No se encontró fila para '{metric}'.")
        else:
            current_section: Optional[str] = None
            servicios_aux_preferred: Optional[List[float]] = None
            servicios_aux_fallback: Optional[List[float]] = None
            fallback_venta_matches: Dict[str, List[float]] = {}
            for desc_norm, values, _ in data_rows:
                section = _detect_section(desc_norm)
                if section:
                    current_section = section
                    continue
                if not desc_norm:
                    continue

                if current_section is None:
                    if _match_row(_TARGET_ROWS_ENERGY["regulados"], desc_norm):
                        fallback_venta_matches["regulados"] = values
                    if _match_row(_TARGET_ROWS_ENERGY["libres"], desc_norm):
                        fallback_venta_matches["libres"] = values
                    if _match_row(_TARGET_ROWS_ENERGY["coes"], desc_norm):
                        fallback_venta_matches["coes"] = values

                if current_section == "venta":
                    if series.get("regulados") == [0.0 for _ in month_columns] and _match_row(_TARGET_ROWS_ENERGY["regulados"], desc_norm):
                        series["regulados"] = values
                    if series.get("libres") == [0.0 for _ in month_columns] and _match_row(_TARGET_ROWS_ENERGY["libres"], desc_norm):
                        series["libres"] = values
                    if series.get("coes") == [0.0 for _ in month_columns] and _match_row(_TARGET_ROWS_ENERGY["coes"], desc_norm):
                        series["coes"] = values

                if _match_row(_TARGET_ROWS_ENERGY["perdidas"], desc_norm):
                    if series.get("perdidas") == [0.0 for _ in month_columns]:
                        series["perdidas"] = values

                if _match_row(["SERVICIOS AUXILIARES"], desc_norm):
                    servicios_aux_preferred = servicios_aux_preferred or values
                    continue
                if _match_row(["CONSUMO PROPIO DE CENTRALES", "CONSUMO PROPIO"], desc_norm):
                    servicios_aux_fallback = servicios_aux_fallback or values

            if servicios_aux_preferred is not None:
                series["servicios_aux"] = servicios_aux_preferred
            elif servicios_aux_fallback is not None:
                series["servicios_aux"] = servicios_aux_fallback

            for metric in ("regulados", "libres", "coes"):
                if all(val == 0 for val in series[metric]) and metric in fallback_venta_matches:
                    series[metric] = fallback_venta_matches[metric]

            for metric in targets:
                if all(val == 0 for val in series[metric]):
                    warnings.append(f"No se encontró fila para '{metric}'.")

        last_with_data = -1
        for midx, present in enumerate(month_presence):
            if present or any(series[m][midx] != 0 for m in targets):
                last_with_data = midx

        active_month_columns = month_columns if last_with_data < 0 else month_columns[: last_with_data + 1]
        active_presence = month_presence if last_with_data < 0 else month_presence[: last_with_data + 1]
        active_month_names = [name for _, name in active_month_columns]

        aligned_months: List[str] = []
        aligned_presence: List[bool] = []
        aligned: Dict[str, List[float]] = {k: [] for k in targets}
        for target_month in MONTH_ORDER:
            if target_month in active_month_names:
                idx = active_month_names.index(target_month)
                aligned_months.append(target_month)
                aligned_presence.append(active_presence[idx] if idx < len(active_presence) else False)
                for metric in targets:
                    aligned[metric].append(series[metric][idx] if idx < len(series[metric]) else 0.0)
            else:
                warnings.append(f"Mes '{target_month}' no encontrado en la tabla. Se usa 0.")
                aligned_months.append(target_month)
                aligned_presence.append(False)
                for metric in targets:
                    aligned[metric].append(0.0)

        if warnings:
            logger.warning("Advertencias al parsear tabla %s: %s", "ventas" if is_sales else "energía", warnings)
        return aligned_months, aligned_presence, aligned, warnings

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
