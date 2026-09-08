"""Private source-field disclosure; never a public research or scoring endpoint."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime

router = APIRouter(prefix='/accounts', tags=['accounts'])


def _account(runtime, account_id):
    if account_id not in {a.id for a in runtime.environment().accounts}:
        raise HTTPException(404, 'Canonical account not found.')


@router.get('/{account_id}/workbook-fields')
def workbook_fields(account_id: str, offset: int = Query(default=0, ge=0, le=2000), runtime: PocRuntime = Depends(get_runtime)):
    _account(runtime, account_id)
    try:
        return runtime.reference_fields.list(account_id, offset=offset)
    except SQLAlchemyError as error:
        raise HTTPException(503, 'Source workbook fields are unavailable; retry this disclosure.') from error


@router.get('/{account_id}/workbook-fields/{version_id}')
def workbook_field_version(account_id: str, version_id: str, runtime: PocRuntime = Depends(get_runtime)):
    _account(runtime, account_id)
    if len(version_id) != 64 or any(c not in '0123456789abcdef' for c in version_id):
        raise HTTPException(404, 'Source version not found in this account scope.')
    try:
        result = runtime.reference_fields.version(account_id, version_id)
    except SQLAlchemyError as error:
        raise HTTPException(503, 'Source version is unavailable; retry this disclosure.') from error
    if result is None:
        raise HTTPException(404, 'Source version not found in this account scope.')
    return result
