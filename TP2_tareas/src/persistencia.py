"""Volcado mínimo del estado en archivos JSON."""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Iterable

from src.gestor import RegistroTarea


logger = logging.getLogger(__name__)


def informar_volcado_anterior(directorio: Path) -> Path | None:
    archivos = sorted(directorio.glob("estado_*.json")) if directorio.exists() else []
    if not archivos:
        logger.info("no se encontró un volcado anterior")
        return None
    ultimo = archivos[-1]
    logger.info("se encontró un volcado anterior: %s", ultimo)
    return ultimo


def volcar_estado(
    directorio: Path, registros: Iterable[RegistroTarea]
) -> Path:
    directorio.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destino = directorio / f"estado_{marca}.json"
    datos = [registro.publica() for registro in registros]
    destino.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("estado guardado en %s", destino)
    return destino

