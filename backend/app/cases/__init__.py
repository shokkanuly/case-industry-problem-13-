"""
Case Engine Layer — the algorithmic core of the Industrial Nervous System.

Each of the 15 industrial cases is implemented as a CaseEngine module that
exposes the same contract: describe(), simulate(), compute(). The registry
below is the single source of truth the API layer serves from.
"""

from app.cases.base import CaseEngine, CaseRegistry

registry = CaseRegistry()


def _load_engines() -> None:
    from app.cases.case01_prospectivity import ProspectivityEngine
    from app.cases.case02_spectral import SpectralAnalyzerEngine
    from app.cases.case03_gradecontrol import GradeControlEngine
    from app.cases.case04_thermal import ThermalShortCircuitEngine
    from app.cases.case05_slope import SlopeStabilityEngine
    from app.cases.case06_blindzone import BlindZoneEngine
    from app.cases.case07_furnace import VanyukovFurnaceEngine
    from app.cases.case08_vibration import VibrationDiagnosticsEngine
    from app.cases.case09_biodiversity import BiodiversityEngine
    from app.cases.case10_meshsync import MeshSyncEngine
    from app.cases.case11_energy import EnergyOptimizerEngine
    from app.cases.case12_perclos import PerclosEngine
    from app.cases.case13_ppe import PPEComplianceEngine
    from app.cases.case14_wagon import WagonCameraEngine
    from app.cases.case15_construction import ConstructionCoreEngine

    for engine_cls in (
        ProspectivityEngine,
        SpectralAnalyzerEngine,
        GradeControlEngine,
        ThermalShortCircuitEngine,
        SlopeStabilityEngine,
        BlindZoneEngine,
        VanyukovFurnaceEngine,
        VibrationDiagnosticsEngine,
        BiodiversityEngine,
        MeshSyncEngine,
        EnergyOptimizerEngine,
        PerclosEngine,
        PPEComplianceEngine,
        WagonCameraEngine,
        ConstructionCoreEngine,
    ):
        registry.register(engine_cls())


_load_engines()

__all__ = ["CaseEngine", "CaseRegistry", "registry"]
