"""Configuración sencilla mediante variables de entorno."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Configuracion:
    workers: int = 3
    procesos_cpu: int = 2
    limite_cola: int = 100
    espera_apagado: float = 10.0
    directorio_estado: Path = Path("estado")

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        return cls(
            workers=max(1, int(os.getenv("TASK_WORKERS", "3"))),
            procesos_cpu=max(1, int(os.getenv("TASK_CPU_WORKERS", "2"))),
            limite_cola=max(1, int(os.getenv("TASK_QUEUE_SIZE", "100"))),
            espera_apagado=max(
                0.1, float(os.getenv("TASK_SHUTDOWN_TIMEOUT", "10"))
            ),
            directorio_estado=Path(os.getenv("TASK_STATE_DIR", "estado")),
        )

