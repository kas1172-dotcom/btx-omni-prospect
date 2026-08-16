from fastapi import APIRouter, Depends, HTTPException

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.monitor.sources import REGISTRY

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/sources")
def sources() -> list[dict]:
    return [{"source_id": item.definition.source_id, "source_name": item.definition.source_name, "source_tier": item.definition.source_tier, "industries_supported": item.definition.industries_supported, "event_types_supported": item.definition.event_types_supported, "cadence": item.definition.cadence, "authentication_requirement": item.definition.authentication_requirement} for item in REGISTRY.values()]


@router.get("/health")
def monitor_health(runtime: PocRuntime = Depends(get_runtime)) -> dict:
    return {
        "sources": runtime.monitor.health,
        "last_runs": runtime.monitor.runs[-20:],
        "clusters": tuple(runtime.monitor.clusters.values()),
        "rejected_observations": tuple(runtime.monitor.rejected[-20:]),
    }


@router.post("/collect/{source_id}")
def collect(source_id: str, runtime: PocRuntime = Depends(get_runtime)) -> dict:
    if source_id not in runtime.monitor.registry:
        raise HTTPException(404, "unknown monitor source")
    return {"run": runtime.monitor.collect(source_id)}
