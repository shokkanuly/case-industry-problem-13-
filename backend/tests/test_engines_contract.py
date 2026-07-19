"""Contract tests: every engine honours the CaseEngine interface."""

import pytest

from app.cases import registry

ALL_IDS = [e.case_id for e in registry.all()]


def test_registry_has_fifteen_cases():
    assert len(registry.all()) == 15
    assert sorted(ALL_IDS) == list(range(1, 16))


@pytest.mark.parametrize("case_id", ALL_IDS)
@pytest.mark.parametrize("scenario", ["normal", "anomaly"])
def test_demo_produces_valid_result(case_id, scenario):
    engine = registry.get(case_id)
    out = engine.demo(scenario)
    result = out["result"]
    assert result["case_id"] == case_id
    assert result["status"] in {"normal", "warning", "critical"}
    assert isinstance(result["headline"], str) and result["headline"]
    assert isinstance(result["metrics"], dict)
    assert isinstance(result["recommendations"], list)


@pytest.mark.parametrize("case_id", ALL_IDS)
def test_describe_has_required_fields(case_id):
    d = registry.get(case_id).describe()
    for field in ("case_id", "slug", "name", "category", "stage", "algorithm"):
        assert d[field], f"case {case_id} missing {field}"
    assert d["stage"] in {"software", "hardware-later", "live"}


@pytest.mark.parametrize("case_id", ALL_IDS)
def test_anomaly_is_at_least_as_severe_as_normal(case_id):
    order = {"normal": 0, "warning": 1, "critical": 2}
    engine = registry.get(case_id)
    normal = engine.demo("normal")["result"]["status"]
    anomaly = engine.demo("anomaly")["result"]["status"]
    assert order[anomaly] >= order[normal], (
        f"case {case_id}: anomaly ({anomaly}) less severe than normal ({normal})"
    )


@pytest.mark.parametrize("case_id", ALL_IDS)
def test_run_matches_demo_compute(case_id):
    """compute(simulate(...)) is deterministic and equals demo()'s result."""
    engine = registry.get(case_id)
    payload = engine.simulate("anomaly")
    r1 = engine.compute(payload).to_dict()
    r2 = engine.compute(payload).to_dict()
    assert r1["status"] == r2["status"]
    assert r1["headline"] == r2["headline"]
