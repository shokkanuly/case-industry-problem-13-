"""Known-answer tests for the scientifically load-bearing algorithm cores."""

import math

import pytest

from app.cases import registry
from app.cases.case05_slope import linear_regression
from app.cases.case08_vibration import fft, iso_zone, rms
from app.cases.spectral_core import cosine_similarity, gaussian_spectrum


# ── Case 05: inverse-velocity (Fukuzono) ──────────────────────────────
def test_linear_regression_exact():
    a, b, r2 = linear_regression([0, 1, 2, 3], [1, 3, 5, 7])  # y = 2x + 1
    assert a == pytest.approx(2.0)
    assert b == pytest.approx(1.0)
    assert r2 == pytest.approx(1.0)


def test_inverse_velocity_predicts_known_failure_time():
    """Synthetic alpha=2 creep with failure at t_f=16.5 must be recovered."""
    engine = registry.get(5)
    result = engine.compute(engine.simulate("anomaly")).to_dict()
    m = result["metrics"]
    assert result["status"] in {"warning", "critical"}
    assert m["time_to_failure_days"] is not None
    predicted_tf = 14.75 + m["time_to_failure_days"]  # last epoch + remaining
    assert predicted_tf == pytest.approx(16.5, abs=1.5)
    assert m["regression_r2"] > 0.6


def test_slope_normal_is_stable():
    engine = registry.get(5)
    result = engine.compute(engine.simulate("normal")).to_dict()
    assert result["status"] == "normal"
    assert result["metrics"]["time_to_failure_days"] is None


# ── Case 08: FFT + ISO 20816-3 ────────────────────────────────────────
def test_fft_recovers_single_tone():
    fs, n, f0 = 64, 64, 8.0
    sig = [complex(math.sin(2 * math.pi * f0 * i / fs), 0) for i in range(n)]
    spec = fft(sig)
    amps = [abs(spec[k]) for k in range(n // 2)]
    peak_bin = max(range(len(amps)), key=lambda k: amps[k])
    assert peak_bin * fs / n == pytest.approx(f0, abs=fs / n)


def test_iso_zone_boundaries():
    assert iso_zone(1.0) == "A"
    assert iso_zone(2.0) == "B"
    assert iso_zone(3.5) == "C"
    assert iso_zone(9.9) == "D"


def test_rms_of_known_sine():
    n = 2048
    sig = [math.sin(2 * math.pi * 5 * i / n) for i in range(n)]
    assert rms(sig) == pytest.approx(1 / math.sqrt(2), abs=1e-2)


def test_vibration_anomaly_flags_unbalance():
    engine = registry.get(8)
    result = engine.compute(engine.simulate("anomaly")).to_dict()
    assert result["metrics"]["iso_zone"] in {"C", "D"}
    assert any("unbalance" in f for f in result["metrics"]["suspected_faults"])


# ── Spectral core (cases 02 / 15) ─────────────────────────────────────
def test_cosine_similarity_identity_and_orthogonal():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)


def test_spectral_classifier_matches_ground_truth():
    engine = registry.get(2)
    payload = engine.simulate("anomaly")  # chalcocite ground truth
    result = engine.compute(payload).to_dict()
    assert result["metrics"]["matched_mineral"] == payload["_ground_truth"]
    assert result["metrics"]["confidence"] > 0.8


def test_construction_core_strength_monotonic():
    from app.cases.case15_construction import sonreb_strength_mpa
    weak = sonreb_strength_mpa(25, 3.5)
    strong = sonreb_strength_mpa(45, 4.8)
    assert strong > weak > 0


# ── Case 11: energy optimizer never does worse than status quo ────────
def test_energy_optimizer_saves_money():
    engine = registry.get(11)
    result = engine.compute(engine.simulate("anomaly")).to_dict()
    assert result["metrics"]["savings_usd"] >= 0
    assert result["metrics"]["peak_demand_kwh"] <= result["metrics"]["peak_cap_kwh"] + 1e-6


# ── Case 10: store-and-forward preserves ordering and delivery ────────
def test_mesh_sync_no_message_loss_across_outage():
    engine = registry.get(10)
    result = engine.compute(engine.simulate("anomaly")).to_dict()
    m = result["metrics"]
    assert m["in_order"] is True
    assert m["exactly_once"] is True
    assert m["events_delivered"] == m["events_total"]


# ── Case 12: PERCLOS ──────────────────────────────────────────────────
def test_perclos_detects_microsleep():
    engine = registry.get(12)
    result = engine.compute(engine.simulate("anomaly")).to_dict()
    assert len(result["metrics"]["microsleep_events"]) >= 1
    assert result["status"] in {"warning", "critical"}


def test_perclos_stationary_suppresses_alert():
    """Eyes-closed but vehicle stopped must not raise a moving-driver alarm."""
    engine = registry.get(12)
    payload = engine.simulate("anomaly")
    payload["speed_kmh"] = 0.0
    result = engine.compute(payload).to_dict()
    assert result["metrics"]["vehicle_moving"] is False
    assert result["status"] == "normal"
