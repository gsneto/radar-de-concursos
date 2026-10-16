"""Distância geográfica honesta: linha reta, desconhecido explícito, sem inventar."""

import json
import tempfile
import unittest
from pathlib import Path

from radar import geography


class CoordinateTest(unittest.TestCase):
    def test_capital_conhecida(self):
        self.assertIsNotNone(geography.coordinates("Salvador", "BA"))
        self.assertIsNotNone(geography.coordinates("Recife", "PE"))

    def test_acentos_e_caixa(self):
        self.assertIsNotNone(geography.coordinates("São Paulo", "SP"))
        self.assertEqual(geography.coordinates("SÃO PAULO", "SP"), geography.coordinates("sao paulo", "sp"))

    def test_municipio_desconhecido(self):
        self.assertIsNone(geography.coordinates("Cidade Inexistente", "BA"))

    def test_uf_ausente(self):
        self.assertIsNone(geography.coordinates("Salvador", None))
        self.assertIsNone(geography.coordinates(None, "BA"))


class DistanceTest(unittest.TestCase):
    def test_haversine_salvador_recife(self):
        a = geography.coordinates("Salvador", "BA")
        b = geography.coordinates("Recife", "PE")
        # ~676 km em linha reta; tolerância ampla.
        self.assertTrue(600 <= geography.haversine_km(a, b) <= 720)

    def test_distancia_nunca_e_rodoviaria(self):
        out = geography.distance_from_reference("Salvador", "BA",
                                                reference={"municipio": "Recife", "uf": "PE"})
        self.assertTrue(out["known"])
        self.assertEqual(out["kind"], "geografica_linha_reta")
        self.assertNotIn("rodovi", json.dumps(out).lower())
        self.assertNotIn("duracao", json.dumps(out).lower())

    def test_desconhecido_explica_motivo(self):
        out = geography.distance_from_reference("Cidade Inexistente", "BA",
                                                reference={"municipio": "Recife", "uf": "PE"})
        self.assertFalse(out["known"])
        self.assertIsNone(out["distance_km"])
        self.assertIn("coordenada", out["reason"])

    def test_sem_referencia(self):
        out = geography.distance_from_reference("Salvador", "BA", reference={})
        self.assertFalse(out["known"])
        self.assertIn("referência", out["reason"])

    def test_sem_municipio_destino(self):
        out = geography.distance_from_reference(None, None,
                                                reference={"municipio": "Recife", "uf": "PE"})
        self.assertFalse(out["known"])
        self.assertIsNotNone(out["reason"])

    def test_zero_quando_mesmo_municipio(self):
        out = geography.distance_from_reference("Recife", "PE",
                                                reference={"municipio": "Recife", "uf": "PE"})
        self.assertEqual(out["distance_km"], 0.0)


class ProviderTest(unittest.TestCase):
    def test_provedor_local_amplia_o_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coords.json"
            path.write_text(json.dumps({"Petrolina": {"uf": "PE", "lat": -9.39, "lon": -40.5}}),
                            encoding="utf-8")
            provider = geography.load_provider(str(path))
        self.assertIsNotNone(geography.coordinates("Petrolina", "PE", provider=provider))
        # Seed continua disponível.
        self.assertIsNotNone(geography.coordinates("Salvador", "BA", provider=provider))

    def test_arquivo_invalido_nao_quebra(self):
        provider = geography.load_provider("caminho/que/nao/existe.json")
        self.assertIsNotNone(geography.coordinates("Salvador", "BA", provider=provider))

    def test_coordenada_invalida_ignorada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coords.json"
            path.write_text(json.dumps({"X": {"uf": "BA", "lat": "não", "lon": 1}}), encoding="utf-8")
            provider = geography.load_provider(str(path))
        self.assertIsNone(geography.coordinates("X", "BA", provider=provider))

    def test_coordenada_nan_ou_fora_de_faixa_ignorada(self):
        # Regressão: NaN e valores fora de faixa não podem virar distância "conhecida".
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coords.json"
            path.write_text(json.dumps({
                "NaNcity": {"uf": "BA", "lat": float("nan"), "lon": -38.0},
                "Foracity": {"uf": "BA", "lat": 999, "lon": -38.0},
                "Infcity": {"uf": "BA", "lat": float("inf"), "lon": -38.0},
            }), encoding="utf-8")
            provider = geography.load_provider(str(path))
        self.assertIsNone(geography.coordinates("NaNcity", "BA", provider=provider))
        self.assertIsNone(geography.coordinates("Foracity", "BA", provider=provider))
        self.assertIsNone(geography.coordinates("Infcity", "BA", provider=provider))
        out = geography.distance_from_reference("NaNcity", "BA",
                                                reference={"municipio": "Recife", "uf": "PE"},
                                                provider=provider)
        self.assertFalse(out["known"])
        self.assertIsNone(out["distance_km"])

    def test_provider_cacheado_por_caminho(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coords.json"
            path.write_text(json.dumps({"Cidade X": {"uf": "BA", "lat": -10.0, "lon": -40.0}}),
                            encoding="utf-8")
            first = geography.load_provider(str(path))
            second = geography.load_provider(str(path))
        self.assertIs(first, second)  # cache evita reler/recopiar o seed


if __name__ == "__main__":
    unittest.main()
