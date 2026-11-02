"""Medición 2: latencia de GET /tareas con CPU directa y con executor."""

import asyncio
from concurrent.futures import ProcessPoolExecutor
import json
import logging
from pathlib import Path
import time

import httpx

from src.api import crear_app
from src.configuracion import Configuracion
from src.ejecutores import hash_iterado


ITERACIONES = 1_500_000
logging.getLogger("httpx").setLevel(logging.WARNING)


async def latencia_get(cliente: httpx.AsyncClient) -> float:
    inicio = time.perf_counter()
    await asyncio.sleep(0.05)
    respuesta = await cliente.get("/tareas")
    respuesta.raise_for_status()
    return time.perf_counter() - inicio - 0.05


async def cpu_directa():
    hash_iterado("medicion", ITERACIONES)


async def cpu_en_executor(pool: ProcessPoolExecutor):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(pool, hash_iterado, "medicion", ITERACIONES)


async def medir():
    config = Configuracion(
        workers=1,
        procesos_cpu=1,
        directorio_estado=Path("/tmp/medicion_estado"),
    )
    app = crear_app(config)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    cliente = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://medicion"
    )
    try:
        inicio = time.perf_counter()
        latencia_directa, _ = await asyncio.gather(
            latencia_get(cliente), cpu_directa()
        )
        duracion_directa = time.perf_counter() - inicio

        with ProcessPoolExecutor(max_workers=1) as pool:
            inicio = time.perf_counter()
            latencia_executor, _ = await asyncio.gather(
                latencia_get(cliente), cpu_en_executor(pool)
            )
            duracion_executor = time.perf_counter() - inicio
    finally:
        await cliente.aclose()
        await lifespan.__aexit__(None, None, None)

    return {
        "iteraciones_hash": ITERACIONES,
        "latencia_get_sin_executor": latencia_directa,
        "latencia_get_con_executor": latencia_executor,
        "duracion_cpu_directa": duracion_directa,
        "duracion_cpu_executor": duracion_executor,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(medir()), indent=2))

