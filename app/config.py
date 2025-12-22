import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
DB_PATH = Path(os.getenv("DB_PATH", ROOT_DIR / "data.db"))
DEFAULT_SOURCE_ID = os.getenv("BALANCE_SOURCE_ID", "balance-xlsx")

ALLOWED_ORIGINS = [
    origin
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin
]

WATCH_DEBOUNCE_SECONDS = float(os.getenv("WATCH_DEBOUNCE_SECONDS", "1.2"))
XLSX_RETRY_COUNT = int(os.getenv("XLSX_RETRY_COUNT", "3"))
XLSX_RETRY_DELAY = float(os.getenv("XLSX_RETRY_DELAY", "0.8"))

MONTH_ORDER = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]
