import asyncio
import unittest

from src.gestor import GestorTareas
from src.modelos import NuevaTarea


async def ejecutor_controlado(tipo, datos):
    if datos.get("fallar"):
        raise ValueError("fallo esperado")
    await asyncio.sleep(float(datos.get("segundos", 0)))
    return datos


class PruebasGestor(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_y_excepcion_actualizan_el_estado(self):
        gestor = GestorTareas(1, 10, ejecutor_controlado)
        await gestor.iniciar()
        lenta = gestor.crear(
            NuevaTarea(tipo="esperar", segundos=1, timeout=0.02)
        )
        await gestor.esperar_pendientes()
        self.assertEqual(lenta.estado, "fallida")
        self.assertIn("timeout", lenta.error)

        async def falla(_tipo, _datos):
            raise ValueError("fallo esperado")

        await gestor.detener(1)
        gestor = GestorTareas(1, 10, falla)
        await gestor.iniciar()
        fallida = gestor.crear(
            NuevaTarea(tipo="esperar", segundos=0, timeout=1)
        )
        await gestor.esperar_pendientes()
        self.assertEqual(fallida.estado, "fallida")
        self.assertIn("ValueError", fallida.error)
        await gestor.detener(1)

    async def test_cancelacion_pendiente_se_respeta_al_iniciar_workers(self):
        gestor = GestorTareas(1, 10, ejecutor_controlado)
        registro = gestor.crear(
            NuevaTarea(tipo="esperar", segundos=1, timeout=2)
        )
        gestor.cancelar(registro.id)
        await gestor.iniciar()
        await gestor.esperar_pendientes()
        self.assertEqual(registro.estado, "cancelada")
        await gestor.detener(1)

    async def test_cola_acotada_rechaza_carga_excesiva(self):
        gestor = GestorTareas(1, 1, ejecutor_controlado)
        gestor.crear(NuevaTarea(tipo="esperar", segundos=0, timeout=1))
        with self.assertRaises(asyncio.QueueFull):
            gestor.crear(
                NuevaTarea(tipo="esperar", segundos=0, timeout=1)
            )


if __name__ == "__main__":
    unittest.main()

