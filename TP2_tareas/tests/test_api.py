import asyncio
from pathlib import Path
import tempfile
import time
import unittest

import httpx

from src.api import crear_app
from src.configuracion import Configuracion


class PruebasAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.app = crear_app(
            Configuracion(
                workers=2,
                procesos_cpu=1,
                limite_cola=20,
                espera_apagado=1,
                directorio_estado=Path(self.temporal.name),
            )
        )
        self.lifespan = self.app.router.lifespan_context(self.app)
        await self.lifespan.__aenter__()
        transport = httpx.ASGITransport(app=self.app)
        self.cliente = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.cliente.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.temporal.cleanup()

    async def test_crear_consultar_listar_y_estadisticas(self):
        respuesta = await self.cliente.post(
            "/tareas",
            json={"tipo": "esperar", "segundos": 0.02, "timeout": 1},
        )
        self.assertEqual(respuesta.status_code, 201)
        creada = respuesta.json()
        self.assertIn(creada["estado"], {"pendiente", "ejecutando"})

        tarea_id = creada["id"]
        await self.app.state.gestor.esperar_pendientes()
        consulta = await self.cliente.get(f"/tareas/{tarea_id}")
        self.assertEqual(consulta.json()["estado"], "completada")

        listado = await self.cliente.get("/tareas", params={"estado": "completada"})
        self.assertEqual([item["id"] for item in listado.json()], [tarea_id])

        estadisticas = (await self.cliente.get("/estadisticas")).json()
        self.assertEqual(estadisticas["total"], 1)
        self.assertEqual(estadisticas["por_estado"]["completada"], 1)

    async def test_cancelar_tarea_en_ejecucion(self):
        creada = (
            await self.cliente.post(
                "/tareas",
                json={"tipo": "esperar", "segundos": 10, "timeout": 20},
            )
        ).json()
        for _ in range(50):
            actual = (await self.cliente.get(f"/tareas/{creada['id']}" )).json()
            if actual["estado"] == "ejecutando":
                break
            await asyncio.sleep(0.01)

        cancelada = await self.cliente.delete(f"/tareas/{creada['id']}")
        self.assertEqual(cancelada.status_code, 200)
        self.assertEqual(cancelada.json()["estado"], "cancelada")
        await asyncio.wait_for(self.app.state.gestor.esperar_pendientes(), 1)

    async def test_post_responde_sin_esperar_la_tarea(self):
        inicio = time.perf_counter()
        respuesta = await self.cliente.post(
            "/tareas",
            json={"tipo": "esperar", "segundos": 0.4, "timeout": 1},
        )
        duracion = time.perf_counter() - inicio

        self.assertEqual(respuesta.status_code, 201)
        self.assertLess(duracion, 0.2)
        self.assertIn(respuesta.json()["estado"], {"pendiente", "ejecutando"})
        await self.app.state.gestor.esperar_pendientes()

    async def test_validacion_y_tarea_inexistente(self):
        invalida = await self.cliente.post(
            "/tareas", json={"tipo": "hashear", "texto": "hola"}
        )
        self.assertEqual(invalida.status_code, 422)
        inexistente = await self.cliente.get("/tareas/no-existe")
        self.assertEqual(inexistente.status_code, 404)


if __name__ == "__main__":
    unittest.main()

