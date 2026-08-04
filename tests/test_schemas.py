import pytest
from pydantic import ValidationError

from app.schemas import ParametrosViajeIn


def params_base(**kwargs) -> dict:
    base = {
        "destino": "San Cristóbal",
        "interes": "naturaleza",
        "intereses": ["naturaleza"],
        "categorias_excluidas": [],
        "comida": "vegetariana",
        "personas": 2,
        "presupuesto": 3000.0,
        "tiempo": "2 dias",
    }
    base.update(kwargs)
    return base


class TestParametrosViajeIn:
    def test_acepta_parametros_validos(self):
        p = ParametrosViajeIn(**params_base())
        assert p.destino == "San Cristóbal"
        assert p.personas == 2

    def test_acepta_valores_none(self):
        p = ParametrosViajeIn(
            destino=None, interes=None, comida=None,
            personas=None, presupuesto=None, tiempo=None,
        )
        assert p.destino is None

    def test_recorta_espacios_en_destino(self):
        p = ParametrosViajeIn(**params_base(destino="  Tuxtla  "))
        assert p.destino == "Tuxtla"

    def test_rechaza_presupuesto_negativo(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(presupuesto=-1))

    def test_rechaza_presupuesto_mayor_a_limite(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(presupuesto=10_000_001))

    def test_rechaza_personas_menor_a_1(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(personas=0))

    def test_rechaza_personas_mayor_a_50(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(personas=51))

    def test_rechaza_destino_mayor_a_150_chars(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(destino="x" * 151))

    def test_rechaza_categoria_invalida_en_intereses(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(intereses=["invalida"]))

    def test_rechaza_mas_de_3_intereses(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(
                intereses=["naturaleza", "cultura", "aventura", "familiar"]
            ))

    def test_rechaza_campos_extra(self):
        with pytest.raises(ValidationError):
            ParametrosViajeIn(**params_base(campo_raro="intruso"))

    def test_elimina_duplicados_en_intereses(self):
        p = ParametrosViajeIn(**params_base(intereses=["naturaleza", "naturaleza"]))
        assert p.intereses.count("naturaleza") == 1

    def test_excluye_interes_si_esta_en_excluidas(self):
        p = ParametrosViajeIn(**params_base(
            interes="naturaleza",
            intereses=["naturaleza"],
            categorias_excluidas=["naturaleza"],
        ))
        assert "naturaleza" not in p.intereses
        assert p.interes is None

    def test_promueve_interes_legacy_a_intereses(self):
        p = ParametrosViajeIn(
            destino=None, interes="cultura", intereses=[],
            categorias_excluidas=[], comida=None,
            personas=1, presupuesto=None, tiempo=None,
        )
        assert "cultura" in p.intereses
