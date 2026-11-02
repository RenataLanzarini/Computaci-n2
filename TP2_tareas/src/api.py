"""Aplicación FastAPI y endpoints de la plataforma."""

from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, HTTPException, Query, status

from src.configuracion import Configuracion
from src.ejecutores import EjecutorTareas
from src.gestor import GestorTareas
from src.modelos import EstadoTarea, Estadisticas, NuevaTarea, TareaPublica
from src.persistencia import informar_volcado_anterior, volcar_estado


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def crear_app(configuracion: Configuracion | None = None) -> FastAPI:
    config = configuracion or Configuracion.desde_entorno()
    ejecutor = EjecutorTareas(config.procesos_cpu)
    gestor = GestorTareas(config.workers, config.limite_cola, ejecutor.ejecutar)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        app.state.gestor = gestor
        informar_volcado_anterior(config.directorio_estado)
        await ejecutor.iniciar()
        await gestor.iniciar()
        try:
            yield
        finally:
            await gestor.detener(config.espera_apagado)
            await ejecutor.cerrar()
            volcar_estado(config.directorio_estado, gestor.tareas.values())

    app = FastAPI(
        title="Plataforma de Tareas Distribuidas",
        version="1.0.0",
        lifespan=ciclo_de_vida,
    )
    app.state.gestor = gestor

    @app.post(
        "/tareas",
        response_model=TareaPublica,
        status_code=status.HTTP_201_CREATED,
    )
    async def crear_tarea(nueva: NuevaTarea):
        try:
            return gestor.crear(nueva).publica()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except asyncio.QueueFull as exc:
            raise HTTPException(status_code=503, detail="cola llena") from exc

    @app.get("/tareas", response_model=list[TareaPublica])
    async def listar_tareas(estado: EstadoTarea | None = Query(default=None)):
        return [item.publica() for item in gestor.listar(estado)]

    @app.get("/tareas/{tarea_id}", response_model=TareaPublica)
    async def obtener_tarea(tarea_id: str):
        registro = gestor.obtener(tarea_id)
        if registro is None:
            raise HTTPException(status_code=404, detail="tarea inexistente")
        return registro.publica()

    @app.delete("/tareas/{tarea_id}", response_model=TareaPublica)
    async def cancelar_tarea(tarea_id: str):
        registro = gestor.cancelar(tarea_id)
        if registro is None:
            raise HTTPException(status_code=404, detail="tarea inexistente")
        return registro.publica()

    @app.get("/estadisticas", response_model=Estadisticas)
    async def obtener_estadisticas():
        return gestor.estadisticas()

    return app


# Uvicorn importa este objeto dentro del contenedor.
app = crear_app()

