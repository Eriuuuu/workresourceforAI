from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.auth import get_current_active_user
from app.api.dependencies.toolbox_auth import verify_toolbox_api_key
from app.models.toolbox_telemetry_model import (
    ToolboxBatchInsertResult,
    ToolboxEvent,
    ToolboxEventBatchCreate,
    ToolboxEventCreate,
    ToolboxEventListResponse,
    ToolboxStatsResponse,
)
from app.models.user_model import User
from app.services.toolbox_telemetry_service import ToolboxTelemetryService

router = APIRouter(tags=["toolbox"])


@router.post("/events", response_model=ToolboxEvent, dependencies=[Depends(verify_toolbox_api_key)])
async def create_toolbox_event(
    event: ToolboxEventCreate,
    service: ToolboxTelemetryService = Depends(),
):
    inserted, created = await service.insert_event(event)
    if not inserted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event already exists",
        )
    return created


@router.post(
    "/events/batch",
    response_model=ToolboxBatchInsertResult,
    dependencies=[Depends(verify_toolbox_api_key)],
)
async def create_toolbox_events_batch(
    payload: ToolboxEventBatchCreate,
    service: ToolboxTelemetryService = Depends(),
):
    result = await service.insert_batch(payload.events)
    return ToolboxBatchInsertResult(**result)


@router.get("/events", response_model=ToolboxEventListResponse)
async def list_toolbox_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    hostname: Optional[str] = None,
    feature_id: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    error_keyword: Optional[str] = None,
    service: ToolboxTelemetryService = Depends(),
    current_user: User = Depends(get_current_active_user),
):
    items, total = await service.query_events(
        skip=skip,
        limit=limit,
        hostname=hostname,
        feature_id=feature_id,
        status=status,
        start_time=start_time,
        end_time=end_time,
        error_keyword=error_keyword,
    )
    return ToolboxEventListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/events/{event_id}", response_model=ToolboxEvent)
async def get_toolbox_event(
    event_id: str,
    service: ToolboxTelemetryService = Depends(),
    current_user: User = Depends(get_current_active_user),
):
    event = await service.get_event_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.get("/hostnames", response_model=List[str])
async def list_toolbox_hostnames(
    service: ToolboxTelemetryService = Depends(),
    current_user: User = Depends(get_current_active_user),
):
    return await service.get_hostnames()


@router.get("/stats", response_model=ToolboxStatsResponse)
async def get_toolbox_stats(
    days: int = Query(30, ge=1, le=180),
    hostname: Optional[str] = None,
    feature_id: Optional[str] = None,
    service: ToolboxTelemetryService = Depends(),
    current_user: User = Depends(get_current_active_user),
):
    return await service.get_stats(days=days, hostname=hostname, feature_id=feature_id)
