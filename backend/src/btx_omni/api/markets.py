"""Authenticated market reads; no network refresh or public account disclosure."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.modules.markets.registry import BY_ID

router = APIRouter(prefix='/markets', tags=['markets'], dependencies=[Depends(principal)])


@router.get('')
def markets(kind: Literal['LEVEL', 'MOM_PERCENT', 'YOY_PERCENT'] = 'LEVEL', moving_average: bool = False,
            runtime: PocRuntime = Depends(get_runtime)) -> dict:
    try:
        return runtime.markets.overview(kind=kind, moving_average=moving_average)
    except SQLAlchemyError:
        raise HTTPException(503, 'Market data storage is unavailable. Existing account data is unaffected.') from None


@router.get('/{series_id}')
def market_series(series_id: str, kind: Literal['LEVEL', 'MOM_PERCENT', 'YOY_PERCENT'] = 'LEVEL',
                  moving_average: bool = False, vintage_id: str | None = Query(default=None, pattern=r'^[a-f0-9]{64}$'),
                  runtime: PocRuntime = Depends(get_runtime)) -> dict:
    if series_id not in BY_ID:
        raise HTTPException(404, 'Unknown market series.')
    try:
        result = runtime.markets.detail(series_id, kind=kind, moving_average=moving_average, vintage_id=vintage_id)
    except SQLAlchemyError:
        raise HTTPException(503, 'Market data storage is unavailable. Retry without changing account context.') from None
    if result is None:
        raise HTTPException(404, 'No collected observations for this series and vintage.')
    return result
