import pytest


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestHistorial:
    def test_historial_vacio(self, client):
        r = client.get("/historial")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_historial_limite_minimo(self, client):
        r = client.get("/historial?limite=1")
        assert r.status_code == 200

    def test_historial_limite_maximo(self, client):
        r = client.get("/historial?limite=100")
        assert r.status_code == 200

    def test_historial_limite_cero_rechazado(self, client):
        r = client.get("/historial?limite=0")
        assert r.status_code == 422

    def test_historial_limite_mayor_a_100_rechazado(self, client):
        r = client.get("/historial?limite=101")
        assert r.status_code == 422

    def test_historial_id_no_existente(self, client):
        r = client.get("/historial/999999")
        assert r.status_code == 404


class TestRecomendar:
    params_validos = {
        "destino": "San Cristóbal de las Casas",
        "interes": "naturaleza",
        "intereses": ["naturaleza"],
        "categorias_excluidas": [],
        "comida": None,
        "personas": 2,
        "presupuesto": 5000.0,
        "tiempo": "2 dias",
    }

    def test_rechaza_campo_extra(self, client):
        payload = {**self.params_validos, "campo_raro": "intruso"}
        r = client.post("/recomendar", json=payload)
        assert r.status_code == 422

    def test_rechaza_presupuesto_negativo(self, client):
        payload = {**self.params_validos, "presupuesto": -1}
        r = client.post("/recomendar", json=payload)
        assert r.status_code == 422

    def test_rechaza_personas_mayor_a_50(self, client):
        payload = {**self.params_validos, "personas": 51}
        r = client.post("/recomendar", json=payload)
        assert r.status_code == 422

    def test_rechaza_destino_muy_largo(self, client):
        payload = {**self.params_validos, "destino": "x" * 151}
        r = client.post("/recomendar", json=payload)
        assert r.status_code == 422

    def test_rechaza_categoria_invalida(self, client):
        payload = {**self.params_validos, "intereses": ["invalida"]}
        r = client.post("/recomendar", json=payload)
        assert r.status_code == 422


class TestAuth:
    def test_sin_auth_requerida_accede_sin_header(self, client):
        # REQUIRE_INTERNAL_AUTH=false (valor por defecto en tests)
        r = client.get("/historial")
        assert r.status_code == 200
