import asyncio
import hashlib
import time
import unittest

import httpx

from src.ejecutores import EjecutorTareas


class PruebasEjecutores(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def responder(pedido: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.05)
            return httpx.Response(200, content=pedido.url.path.encode())

        self.cliente = httpx.AsyncClient(
            transport=httpx.MockTransport(responder)
        )
        self.ejecutor = EjecutorTareas(1, cliente=self.cliente)
        await self.ejecutor.iniciar()

    async def asyncTearDown(self):
        await self.ejecutor.cerrar()
        await self.cliente.aclose()

    async def test_descargas_se_ejecutan_concurrentemente(self):
        inicio = time.perf_counter()
        resultados = await self.ejecutor.ejecutar(
            "descargar",
            {"urls": [f"https://ejemplo.test/{n}" for n in range(3)]},
        )
        duracion = time.perf_counter() - inicio

        self.assertLess(duracion, 0.13)
        self.assertEqual(len(resultados), 3)
        self.assertTrue(all(item["estado_http"] == 200 for item in resultados))
        self.assertTrue(all(item["tamano_bytes"] == 2 for item in resultados))

    async def test_hash_iterado_usa_el_executor_y_devuelve_resultado(self):
        resultado = await self.ejecutor.ejecutar(
            "hashear", {"texto": "hola", "iteraciones": 2}
        )
        esperado = hashlib.sha256(
            hashlib.sha256(b"hola").digest()
        ).hexdigest()
        self.assertEqual(resultado["hash"], esperado)
        self.assertEqual(resultado["iteraciones"], 2)

