"""
Case Engine Routes — the algorithmic core exposed over HTTP.

    GET  /api/cases                  list all 15 case engines (descriptors + briefs)
    GET  /api/cases/{id}             one engine's descriptor + input schema + brief
    GET  /api/cases/{id}/source      the engine's actual Python source code
    GET  /api/cases/{id}/demo        run a built-in synthetic scenario end-to-end
    POST /api/cases/{id}/run         run the engine over a caller-supplied payload

Every engine is exercisable with zero hardware: /demo feeds the engine its
own synthetic scenario, /run accepts real field data in the same schema.
"""

import inspect
import json
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.cases import registry
from app.middleware import verify_api_key

router = APIRouter(prefix="/api/cases", tags=["cases"])

# Problem / solution / stage-1 briefs shown on the Solutions Hub
_BRIEFS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cases", "case_briefs.json")
try:
    with open(_BRIEFS_PATH, encoding="utf-8") as _f:
        BRIEFS: Dict[str, Dict[str, str]] = json.load(_f)
except Exception:
    BRIEFS = {}


def _describe_with_brief(engine) -> Dict[str, Any]:
    d = engine.describe()
    d["brief"] = BRIEFS.get(str(engine.case_id), {})
    return d


class RunRequest(BaseModel):
    payload: Dict[str, Any]


@router.get("")
async def list_cases(_: str = Depends(verify_api_key)):
    """List every registered case engine with its descriptor and brief."""
    engines = registry.all()
    return {
        "count": len(engines),
        "cases": [_describe_with_brief(e) for e in engines],
    }


@router.get("/{case_id}")
async def get_case(case_id: int, _: str = Depends(verify_api_key)):
    engine = registry.get(case_id)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"No case engine with id {case_id}")
    return _describe_with_brief(engine)


@router.get("/{case_id}/source")
async def get_case_source(case_id: int, _: str = Depends(verify_api_key)):
    """Return the engine's actual implementation source, straight from the module."""
    engine = registry.get(case_id)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"No case engine with id {case_id}")
    module = inspect.getmodule(type(engine))
    try:
        source = inspect.getsource(module)
        filename = os.path.basename(module.__file__)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Source unavailable: {exc}") from exc
    return {
        "case_id": case_id,
        "filename": filename,
        "language": "python",
        "lines": source.count("\n") + 1,
        "source": source,
    }


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
