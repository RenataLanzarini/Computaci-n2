"""Implementación de las tres tareas obligatorias."""

import asyncio
from concurrent.futures import ProcessPoolExecutor
import hashlib
import time
from typing import Any

import httpx


def hash_iterado(texto: str, iteraciones: int) -> str:
    """Trabajo CPU-bound puro; debe ejecutarse fuera del event loop."""
    valor = texto.encode("utf-8")
    for _ in range(iteraciones):
        valor = hashlib.sha256(valor).digest()
    return valor.hex()


class EjecutorTareas:
    def __init__(
        self,
        procesos_cpu: int,
        cliente: httpx.AsyncClient | None = None,
    ) -> None:
        self._procesos_cpu = procesos_cpu
        self._pool: ProcessPoolExecutor | None = None
        self._cliente_externo = cliente
        self._cliente: httpx.AsyncClient | None = cliente

    async def iniciar(self) -> None:
        self._pool = ProcessPoolExecutor(max_workers=self._procesos_cpu)
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(20.0),
            )

    async def cerrar(self) -> None:
        if self._cliente is not None and self._cliente_externo is None:
            await self._cliente.aclose()
        self._cliente = None
        if self._pool is not None:
            pool = self._pool
            self._pool = None
            await asyncio.to_thread(
                pool.shutdown, wait=True, cancel_futures=True
            )

    async def ejecutar(self, tipo: str, datos: dict[str, Any]) -> Any:
        if tipo == "esperar":
            segundos = float(datos["segundos"])
            await asyncio.sleep(segundos)
            return {"segundos_esperados": segundos}
        if tipo == "descargar":
            return await self._descargar(datos["urls"])
        if tipo == "hashear":
            if self._pool is None:
                raise RuntimeError("el executor CPU no está iniciado")
            loop = asyncio.get_running_loop()
            resultado = await loop.run_in_executor(
                self._pool,
                hash_iterado,
                datos["texto"],
                int(datos["iteraciones"]),
            )
            return {
                "hash": resultado,
                "iteraciones": int(datos["iteraciones"]),
            }
        raise ValueError(f"tipo de tarea desconocido: {tipo}")

    async def _descargar(self, urls: list[str]) -> list[dict[str, Any]]:
        if self._cliente is None:
            raise RuntimeError("el cliente HTTP no está iniciado")

        async def una(url: str) -> dict[str, Any]:
            inicio = time.perf_counter()
            try:
                respuesta = await self._cliente.get(url)
                return {
                    "url": url,
                    "estado_http": respuesta.status_code,
                    "tamano_bytes": len(respuesta.content),
                    "tiempo_segundos": time.perf_counter() - inicio,
                }
            except httpx.RequestError as exc:
                return {
                    "url": url,
                    "error": f"{type(exc).__name__}: {exc}",
                    "tiempo_segundos": time.perf_counter() - inicio,
                }

        resultados = await asyncio.gather(*(una(url) for url in urls))
        if all("error" in item for item in resultados):
            raise RuntimeError("fallaron todas las descargas")
        return resultados

