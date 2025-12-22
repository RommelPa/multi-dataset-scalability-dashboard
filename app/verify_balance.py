import argparse
import logging
from pathlib import Path

from .etl import parse_balance_workbook

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify_balance")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica extracción BALANCE 2016-2025 desde un Excel con hojas por año.")
    parser.add_argument("excel_path", type=Path, help="Ruta del archivo Excel fuente (con hojas BALANCE DE ENERGÍA EN MWh - AÑO YYYY)")
    args = parser.parse_args()

    if not args.excel_path.exists():
        logger.error("Archivo no encontrado: %s", args.excel_path)
        return 1

    results = parse_balance_workbook(args.excel_path)
    found_years = {r.year: r for r in results}
    exit_code = 0

    for year in range(2016, 2026):
        result = found_years.get(year)
        if not result:
            logger.warning("year %s: MISSING (no se encontró hoja en el Excel)", year)
            exit_code = 1
            continue

        month_count = len(result.observed_months)
        monthly_ok = []
        for idx, month in enumerate(result.observed_months):
            total_calc = result.regulados[idx] + result.libres[idx] + result.coes[idx]
            monthly_ok.append(f"{month}: total={total_calc:.1f} (reg={result.regulados[idx]:.1f}, lib={result.libres[idx]:.1f}, coes={result.coes[idx]:.1f})")

        cum_reg = sum(result.regulados[:month_count])
        cum_lib = sum(result.libres[:month_count])
        cum_coes = sum(result.coes[:month_count])
        cum_aux = sum(result.servicios_aux[:month_count])
        cum_perd = sum(result.perdidas[:month_count])
        logger.info(
            "year %s: OK (months=%s, last=%s) | acumulado GWh: regulados=%.1f libres=%.1f coes=%.1f servicios_aux=%.1f perdidas=%.1f",
            year,
            month_count,
            result.observed_months[-1] if result.observed_months else "-",
            cum_reg / 1000,
            cum_lib / 1000,
            cum_coes / 1000,
            cum_aux / 1000,
            cum_perd / 1000,
        )
        logger.debug("  mensual -> %s", "; ".join(monthly_ok))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
