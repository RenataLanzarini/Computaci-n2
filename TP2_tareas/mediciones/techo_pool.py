"""Medición 3: carga creciente sobre la API con dos procesos CPU."""

import asyncio
import json
import logging
from pathlib import Path
import tempfile
import time

import httpx

from src.api import crear_app
from src.configuracion import Configuracion


CANTIDADES = (1, 2, 4, 8, 16)
ITERACIONES = 250_000
logging.getLogger("httpx").setLevel(logging.WARNING)


async def esperar_final(cliente: httpx.AsyncClient, tarea_id: str):
    while True:
        tarea = (await cliente.get(f"/tareas/{tarea_id}")).json()
        if tarea["estado"] in {"completada", "fallida", "cancelada"}:
            return tarea
        await asyncio.sleep(0.01)


async def medir():
    resultados = []
    with tempfile.TemporaryDirectory() as temporal:
        app = crear_app(
            Configuracion(
                workers=16,
                procesos_cpu=2,
                limite_cola=100,
                espera_apagado=10,
                directorio_estado=Path(temporal),
            )
        )
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        cliente = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://medicion"
        )
        try:
            for cantidad in CANTIDADES:
                inicio = time.perf_counter()
                respuestas = await asyncio.gather(*(
                    cliente.post(
                        "/tareas",
                        json={
                            "tipo": "hashear",
                            "texto": f"carga-{cantidad}-{n}",
                            "iteraciones": ITERACIONES,
                            "timeout": 60,
                        },
                    )
                    for n in range(cantidad)
                ))
                ids = [respuesta.json()["id"] for respuesta in respuestas]
                tareas = await asyncio.gather(*(
                    esperar_final(cliente, tarea_id) for tarea_id in ids
                ))
                duracion = time.perf_counter() - inicio
                resultados.append({
                    "tareas": cantidad,
                    "tiempo_total": duracion,
                    "tiempo_por_tarea": duracion / cantidad,
                    "completadas": sum(
                        tarea["estado"] == "completada" for tarea in tareas
                    ),
                })
        finally:
            await cliente.aclose()
            await lifespan.__aexit__(None, None, None)
    return {
        "procesos_cpu": 2,
        "iteraciones_por_tarea": ITERACIONES,
        "resultados": resultados,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(medir()), indent=2))

