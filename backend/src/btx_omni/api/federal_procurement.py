from fastapi import APIRouter, Depends, Query

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.modules.federal_procurement import procurement_projection

router = APIRouter(prefix="/federal-procurement", tags=["federal-procurement"])


@router.get("")
def federal_procurement(
    notice_type: str | None = None,
    sources_sought: bool | None = Query(default=None),
    naics: str | None = None,
    set_aside: str | None = None,
    deadline_bucket: str | None = None,
    sector: str | None = None,
    minimum_relevance: int | None = None,
    fiscal_year: int | None = None,
    runtime: PocRuntime = Depends(get_runtime),
) -> dict:
    return procurement_projection(
        runtime,
        notice_type=notice_type,
        sources_sought=sources_sought,
        naics=naics,
        set_aside=set_aside,
        deadline_bucket=deadline_bucket,
        sector=sector,
        minimum_relevance=minimum_relevance,
        fiscal_year=fiscal_year,
    )
