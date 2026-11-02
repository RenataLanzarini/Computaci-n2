"""Cola, workers y ciclo de vida de las tareas."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Awaitable, Callable
from uuid import uuid4

from src.modelos import EstadoTarea, NuevaTarea


logger = logging.getLogger(__name__)
Ejecutor = Callable[[str, dict[str, Any]], Awaitable[Any]]


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RegistroTarea:
    id: str
    tipo: str
    datos: dict[str, Any]
    timeout: float
    estado: EstadoTarea = "pendiente"
    resultado: Any | None = None
    error: str | None = None
    creada: str = field(default_factory=ahora_iso)
    iniciada: str | None = None
    finalizada: str | None = None
    worker: int | None = None
    duracion: float | None = None

    def publica(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "estado": self.estado,
            "datos": self.datos,
            "timeout": self.timeout,
            "resultado": self.resultado,
            "error": self.error,
            "creada": self.creada,
            "iniciada": self.iniciada,
            "finalizada": self.finalizada,
            "worker": self.worker,
        }


class GestorTareas:
    def __init__(
        self,
        cantidad_workers: int,
        limite_cola: int,
        ejecutor: Ejecutor,
    ) -> None:
        self.cantidad_workers = cantidad_workers
        self.cola: asyncio.Queue[str] = asyncio.Queue(maxsize=limite_cola)
        self.tareas: dict[str, RegistroTarea] = {}
        self._ejecutor = ejecutor
        self._workers: list[asyncio.Task[None]] = []
        self._ejecuciones: dict[str, asyncio.Task[Any]] = {}
        self._aceptando = True
        self._ocupados = 0

    async def iniciar(self) -> None:
        self._aceptando = True
        self._workers = [
            asyncio.create_task(self._worker(numero), name=f"worker-{numero}")
            for numero in range(self.cantidad_workers)
        ]

    def crear(self, nueva: NuevaTarea) -> RegistroTarea:
        if not self._aceptando:
            raise RuntimeError("el servicio está cerrando")
        registro = RegistroTarea(
            id=str(uuid4()),
            tipo=nueva.tipo,
            datos=nueva.datos(),
            timeout=nueva.timeout,
        )
        self.cola.put_nowait(registro.id)
        self.tareas[registro.id] = registro
        return registro

    def obtener(self, tarea_id: str) -> RegistroTarea | None:
        return self.tareas.get(tarea_id)

    def listar(self, estado: EstadoTarea | None = None) -> list[RegistroTarea]:
        registros = list(self.tareas.values())
        if estado is not None:
            registros = [item for item in registros if item.estado == estado]
        return registros

    def cancelar(self, tarea_id: str) -> RegistroTarea | None:
        registro = self.obtener(tarea_id)
        if registro is None:
            return None
        if registro.estado in {"completada", "fallida", "cancelada"}:
            return registro
        estado_anterior = registro.estado
        registro.estado = "cancelada"
        registro.error = "cancelada por el usuario"
        if registro.tipo == "hashear" and estado_anterior == "ejecutando":
            registro.error += (
                "; el cálculo ya iniciado en el executor puede continuar "
                "hasta terminar"
            )
        registro.finalizada = ahora_iso()
        ejecucion = self._ejecuciones.get(tarea_id)
        if ejecucion is not None:
            ejecucion.cancel()
        return registro

    def estadisticas(self) -> dict[str, Any]:
        conteos = {
            estado: 0
            for estado in (
                "pendiente",
                "ejecutando",
                "completada",
                "fallida",
                "cancelada",
            )
        }
        duraciones = []
        for registro in self.tareas.values():
            conteos[registro.estado] += 1
            if registro.duracion is not None:
                duraciones.append(registro.duracion)
        promedio = sum(duraciones) / len(duraciones) if duraciones else None
        return {
            "total": len(self.tareas),
            "por_estado": conteos,
            "tiempo_promedio_segundos": promedio,
            "workers_totales": self.cantidad_workers,
            "workers_ocupados": self._ocupados,
            "tareas_en_cola": self.cola.qsize(),
            "aceptando_tareas": self._aceptando,
        }

    async def esperar_pendientes(self) -> None:
        await self.cola.join()

    async def detener(self, limite: float) -> None:
        self._aceptando = False
        try:
            await asyncio.wait_for(self.cola.join(), timeout=limite)
        except TimeoutError:
            for tarea_id, ejecucion in list(self._ejecuciones.items()):
                registro = self.tareas[tarea_id]
                if registro.estado == "ejecutando":
                    registro.estado = "cancelada"
                    registro.error = "cancelada durante el apagado"
                    registro.finalizada = ahora_iso()
                ejecucion.cancel()
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def _worker(self, numero: int) -> None:
        while True:
            tarea_id = await self.cola.get()
            try:
                registro = self.tareas[tarea_id]
                if registro.estado == "cancelada":
                    continue
                await self._procesar(registro, numero)
            finally:
                self.cola.task_done()

    async def _procesar(self, registro: RegistroTarea, numero: int) -> None:
        loop = asyncio.get_running_loop()
        inicio = loop.time()
        registro.estado = "ejecutando"
        registro.iniciada = ahora_iso()
        registro.worker = numero
        self._ocupados += 1
        ejecucion = asyncio.create_task(
            self._ejecutor(registro.tipo, registro.datos),
            name=f"ejecucion-{registro.id}",
        )
        self._ejecuciones[registro.id] = ejecucion
        try:
            registro.resultado = await asyncio.wait_for(
                ejecucion, timeout=registro.timeout
            )
            if registro.estado != "cancelada":
                registro.estado = "completada"
        except TimeoutError:
            registro.estado = "fallida"
            registro.error = f"timeout de {registro.timeout:g} segundos"
        except asyncio.CancelledError:
            if registro.estado != "cancelada":
                raise
        except Exception as exc:  # El worker debe convertir el fallo en estado.
            logger.exception("falló la tarea %s", registro.id)
            registro.estado = "fallida"
            registro.error = f"{type(exc).__name__}: {exc}"
        finally:
            registro.finalizada = ahora_iso()
            registro.duracion = loop.time() - inicio
            self._ocupados -= 1
            self._ejecuciones.pop(registro.id, None)

