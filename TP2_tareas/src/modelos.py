"""Modelos HTTP y estados permitidos por la consigna."""

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


EstadoTarea = Literal[
    "pendiente", "ejecutando", "completada", "fallida", "cancelada"
]
TipoTarea = Literal["descargar", "hashear", "esperar"]


class NuevaTarea(BaseModel):
    tipo: TipoTarea
    urls: list[HttpUrl] | None = None
    texto: str | None = None
    iteraciones: int | None = Field(default=None, ge=1)
    segundos: float | None = Field(default=None, ge=0)
    timeout: float = Field(default=30.0, gt=0, le=3600)

    @model_validator(mode="after")
    def validar_datos_del_tipo(self) -> "NuevaTarea":
        if self.tipo == "descargar" and not self.urls:
            raise ValueError("descargar requiere una lista no vacía de urls")
        if self.tipo == "hashear":
            if self.texto is None or self.iteraciones is None:
                raise ValueError("hashear requiere texto e iteraciones")
        if self.tipo == "esperar" and self.segundos is None:
            raise ValueError("esperar requiere segundos")
        return self

    def datos(self) -> dict[str, Any]:
        valores = self.model_dump(
            mode="json", exclude={"tipo", "timeout"}, exclude_none=True
        )
        return valores


class TareaPublica(BaseModel):
    id: str
    tipo: TipoTarea
    estado: EstadoTarea
    datos: dict[str, Any]
    timeout: float
    resultado: Any | None = None
    error: str | None = None
    creada: str
    iniciada: str | None = None
    finalizada: str | None = None
    worker: int | None = None


class Estadisticas(BaseModel):
    total: int
    por_estado: dict[str, int]
    tiempo_promedio_segundos: float | None
    workers_totales: int
    workers_ocupados: int
    tareas_en_cola: int
    aceptando_tareas: bool

