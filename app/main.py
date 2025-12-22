import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Callable, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import ALLOWED_ORIGINS, DATA_DIR, DEFAULT_SOURCE_ID, MONTH_ORDER
from .db import fetch_balance_year, init_db, list_balance_years, list_sources, save_balance_rows, upsert_source
from .etl import start_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class EventBroker:
    def __init__(self):
        self.subscribers: List[asyncio.Queue] = []

    async def publish(self, event: Dict) -> None:
        if not self.subscribers:
            return
        for queue in list(self.subscribers):
            await queue.put(event)

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self.subscribers:
            self.subscribers.remove(queue)


broker = EventBroker()
observer = None
loop: asyncio.AbstractEventLoop | None = None

app = FastAPI(title="Multi-dataset Scalability Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _dispatch_event(event: Dict) -> None:
    if not loop:
        return
    event.setdefault("ts", datetime.utcnow().isoformat())
    asyncio.run_coroutine_threadsafe(broker.publish(event), loop)


def _seed_if_empty() -> None:
    years = list_balance_years()
    if years:
        return
    logger.warning("Base de datos vacía. Se generan datos sintéticos de ejemplo.")
    months = MONTH_ORDER
    for year in (2023, 2024, 2025):
        regulados = [52000 + idx * 500 for idx, _ in enumerate(months)]
        libres = [81000 + idx * 650 for idx, _ in enumerate(months)]
        coes = [9500 + idx * 120 for idx, _ in enumerate(months)]
        servicios_aux = [1500 + idx * 30 for idx, _ in enumerate(months)]
        perdidas = [2200 + idx * 35 for idx, _ in enumerate(months)]
        save_balance_rows(year, DEFAULT_SOURCE_ID, months, regulados, libres, coes, servicios_aux, perdidas, observed_months=months)
        upsert_source(DEFAULT_SOURCE_ID, "balance", "sample_balance.xlsx", datetime.utcnow().isoformat())
        _dispatch_event(
            {
                "type": "DATASET_UPDATED",
                "dataset_id": "balance",
                "source_id": DEFAULT_SOURCE_ID,
                "year": year,
                "message": "Datos de ejemplo generados",
            }
        )


class SourcePayload(BaseModel):
    source_id: str = Field(..., description="Identificador único de la fuente")
    dataset_id: str = Field(..., description="Dataset asociado (balance, hidrologia, etc.)")
    file_name: str | None = Field(default=None, description="Nombre del archivo Excel")
    enabled: bool = True


@app.on_event("startup")
async def on_startup():
    global observer, loop
    loop = asyncio.get_running_loop()
    init_db()
    _seed_if_empty()
    observer = start_watcher(_dispatch_event, source_id=DEFAULT_SOURCE_ID)
    logger.info("Aplicación iniciada. DATA_DIR=%s", DATA_DIR)


@app.on_event("shutdown")
def on_shutdown():
    if observer:
        observer.stop()
        observer.join(timeout=2)


@app.get("/api/balance/years")
async def get_balance_years():
    return {"years": list_balance_years()}


@app.get("/api/balance/{year}")
async def get_balance_for_year(year: int):
    years = list_balance_years()
    if year not in years:
        raise HTTPException(status_code=404, detail=f"No existe data para el año {year}")
    data = fetch_balance_year(year)
    data["source_id"] = DEFAULT_SOURCE_ID
    return data


@app.get("/api/sources")
async def get_sources():
    return {"sources": list_sources()}


@app.post("/api/sources")
async def register_source(payload: SourcePayload):
    upsert_source(
        payload.source_id,
        payload.dataset_id,
        payload.file_name or "",
        datetime.utcnow().isoformat(),
    )
    _dispatch_event(
        {
            "type": "DATASET_UPDATED",
            "dataset_id": payload.dataset_id,
            "source_id": payload.source_id,
            "message": f"Fuente {payload.source_id} registrada",
        }
    )
    return {"status": "registered"}


@app.get("/api/events")
async def stream_events() -> StreamingResponse:
    async def event_generator(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        finally:
            broker.unsubscribe(queue)

    queue = await broker.subscribe()
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(queue), headers=headers, media_type="text/event-stream")


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok"}
