"""Preferências geográficas: validação, defaults e rejeição de dados pessoais arbitrários."""

import unittest

from radar import preferences


class PreferencesTest(unittest.TestCase):
    def test_defaults(self):
        out = preferences.load({})
        self.assertEqual(out["interest_states"], ["BA", "PE"])
        self.assertEqual(out["practical_distance_km"], 300)
        self.assertEqual(out["priority"], "equilibrado")
        self.assertIsNone(out["reference_municipio"])

    def test_validacao_normaliza(self):
        out = preferences.validate({"reference_uf": "ba", "interest_states": ["pe", "BA"],
                                    "practical_distance_km": 150, "priority": "potencial"})
        self.assertEqual(out["reference_uf"], "BA")
        self.assertEqual(out["interest_states"], ["BA", "PE"])
        self.assertEqual(out["practical_distance_km"], 150)
        self.assertEqual(out["priority"], "potencial")

    def test_uf_invalida_rejeitada(self):
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"reference_uf": "ZZ"})
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"interest_states": ["XX"]})

    def test_distancia_invalida_rejeitada(self):
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"practical_distance_km": -1})
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"practical_distance_km": True})
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"practical_distance_km": "300"})

    def test_priority_invalida(self):
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"priority": "rapido"})

    def test_campo_desconhecido_rejeitado(self):
        # Evita gravar dados pessoais arbitrários (ex.: endereço) no config.
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"endereco_residencial": "Rua X, 123"})

    def test_endereco_residencial_rejeitado(self):
        # Regressão: o município de referência não pode ser um endereço.
        for value in ("Rua das Flores 123, apto 45", "Avenida Brasil, 1000", "Bairro Centro",
                      "CEP 40000-000"):
            with self.assertRaises(preferences.PreferenceError):
                preferences.validate({"reference_municipio": value})

    def test_municipio_valido_aceito(self):
        self.assertEqual(preferences.validate({"reference_municipio": "Paulo Afonso"})["reference_municipio"],
                         "Paulo Afonso")

    def test_coordinates_path_default_e_validacao(self):
        self.assertIsNone(preferences.load({})["coordinates_path"])
        self.assertEqual(preferences.validate({"coordinates_path": "/tmp/coords.json"})["coordinates_path"],
                         "/tmp/coords.json")
        with self.assertRaises(preferences.PreferenceError):
            preferences.validate({"coordinates_path": "   "})

    def test_defaults_nao_sao_mutados(self):
        # Regressão: mutar o resultado não pode contaminar os defaults globais.
        prefs = preferences.load({})
        prefs["interest_states"].append("XX")
        self.assertEqual(preferences.load({})["interest_states"], ["BA", "PE"])

    def test_config_corrompida_cai_em_defaults(self):
        out = preferences.load({"preferences": {"priority": "inexistente"}})
        self.assertEqual(out["priority"], "equilibrado")

    def test_config_nao_dict_cai_em_defaults(self):
        self.assertEqual(preferences.load({"preferences": "texto"})["priority"], "equilibrado")


if __name__ == "__main__":
    unittest.main()
