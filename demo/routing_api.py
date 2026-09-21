"""Authenticated-host road routing using the shared local/cancel boundary."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

try:
    import cad_api as cad
except ImportError:
    from demo import cad_api as cad

ROOT = Path(__file__).resolve().parents[1]
router = APIRouter(dependencies=[Depends(cad.local_request)])


class RouteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: dict


@router.get("/engineering/routes")
def page():
    return FileResponse(ROOT / "demo/static/engineering-routing.html", headers={"Cache-Control": "no-cache"})


@router.post("/api/engineering/routes/calculate")
async def calculate(request: Request):
    from packing_assistant.engineering.routing import calculate_route
    body = await cad.read_json(request, RouteIn)

    def run():
        try:
            return calculate_route(body.model)
        except ImportError as exc:
            raise HTTPException(503, str(exc)) from exc

    return await cad.operation(request, run)


@router.post("/api/engineering/routes/operations/{operation_id}/cancel")
def cancel(operation_id: str):
    return cad.cancel_import(operation_id)
