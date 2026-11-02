from pathlib import Path
import tempfile
import unittest

from src.gestor import RegistroTarea
from src.persistencia import informar_volcado_anterior, volcar_estado


class PruebasPersistencia(unittest.TestCase):
    def test_vuelca_estado_y_detecta_el_archivo_anterior(self):
        with tempfile.TemporaryDirectory() as temporal:
            directorio = Path(temporal)
            registro = RegistroTarea(
                id="abc",
                tipo="esperar",
                datos={"segundos": 1},
                timeout=2,
            )
            destino = volcar_estado(directorio, [registro])
            self.assertTrue(destino.exists())
            self.assertIn('"id": "abc"', destino.read_text(encoding="utf-8"))
            self.assertEqual(informar_volcado_anterior(directorio), destino)


if __name__ == "__main__":
    unittest.main()

