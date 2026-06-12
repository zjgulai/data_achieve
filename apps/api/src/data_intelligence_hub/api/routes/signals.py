from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.signal import (
    SignalResponse,
    SignalSnapshotCompareResponse,
    SnapshotCompareItem,
    SnapshotMetricDiff,
)
from data_intelligence_hub.services.exceptions import (
    SignalNotFoundError,
    SignalSnapshotCompareNotAvailableError,
)
from data_intelligence_hub.services.signal_service import (
    get_signal_or_raise,
    get_signal_snapshot_compare,
    get_signals,
)

router = APIRouter(tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def list_signal_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
    type_filter: Annotated[str | None, Query(alias="type")] = None,
    severity: Annotated[str | None, Query()] = None,
) -> list[SignalResponse]:
    signals = await get_signals(
        session,
        context.workspace,
        project_id=project_id,
        entity_id=entity_id,
        signal_type=type_filter,
        severity=severity,
    )
    return [SignalResponse.from_model(signal) for signal in signals]


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal_item(
    signal_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SignalResponse:
    try:
        signal = await get_signal_or_raise(session, context.workspace, signal_id)
    except SignalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return SignalResponse.from_model(signal)


@router.get("/{signal_id}/snapshot-compare", response_model=SignalSnapshotCompareResponse)
async def get_signal_snapshot_compare_item(
    signal_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SignalSnapshotCompareResponse:
    try:
        compare = await get_signal_snapshot_compare(session, context.workspace, signal_id)
    except SignalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except SignalSnapshotCompareNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return SignalSnapshotCompareResponse(
        signal_id=compare.signal.id,
        entity_id=compare.signal.entity_id,
        signal_type=compare.signal.signal_type,
        previous_snapshot=SnapshotCompareItem.from_model(compare.previous_snapshot),
        current_snapshot=SnapshotCompareItem.from_model(compare.current_snapshot),
        metrics_diff=[
            SnapshotMetricDiff(
                metric=item.metric,
                previous_value=item.previous_value,
                current_value=item.current_value,
                delta=item.delta,
                delta_ratio=item.delta_ratio,
            )
            for item in compare.metrics_diff
        ],
    )
