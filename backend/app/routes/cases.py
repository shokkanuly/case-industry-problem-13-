"""
Case Engine Routes — the algorithmic core exposed over HTTP.

    GET  /api/cases                  list all 15 case engines (descriptors)
    GET  /api/cases/{id}             one engine's descriptor + input schema
    GET  /api/cases/{id}/demo        run a built-in synthetic scenario end-to-end
    POST /api/cases/{id}/run         run the engine over a caller-supplied payload

Every engine is exercisable with zero hardware: /demo feeds the engine its
own synthetic scenario, /run accepts real field data in the same schema.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.cases import registry
from app.middleware import verify_api_key

router = APIRouter(prefix="/api/cases", tags=["cases"])


class RunRequest(BaseModel):
    payload: Dict[str, Any]


@router.get("")
async def list_cases(_: str = Depends(verify_api_key)):
    """List every registered case engine with its descriptor."""
    engines = registry.all()
    return {
        "count": len(engines),
        "cases": [e.describe() for e in engines],
    }


@router.get("/{case_id}")
async def get_case(case_id: int, _: str = Depends(verify_api_key)):
    engine = registry.get(case_id)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"No case engine with id {case_id}")
    return engine.describe()


@router.get("/{case_id}/demo")
async def demo_case(
    case_id: int,
    scenario: str = Query("anomaly", pattern="^(normal|anomaly)$"),
    _: str = Depends(verify_api_key),
):
    """Run the engine's built-in synthetic scenario and return input + result."""
    engine = registry.get(case_id)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"No case engine with id {case_id}")
    try:
        return engine.demo(scenario)
    except Exception as exc:  # surface engine errors as 422, not 500
        raise HTTPException(status_code=422, detail=f"Engine error: {exc}") from exc


@router.post("/{case_id}/run")
async def run_case(case_id: int, req: RunRequest, _: str = Depends(verify_api_key)):
    """Run the engine over a caller-supplied payload matching its input schema."""
    engine = registry.get(case_id)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"No case engine with id {case_id}")
    try:
        result = engine.compute(req.payload)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"Missing field: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Engine error: {exc}") from exc
    return result.to_dict()
