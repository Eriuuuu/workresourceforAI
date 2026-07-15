from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ToolboxEventCreate(BaseModel):
    event_id: str = Field(..., min_length=8, max_length=64)
    client_time: str = Field(..., description="客户端本地时间，格式 YYYY-MM-DD HH:MM:SS")
    hostname: str = Field(..., min_length=1, max_length=128)
    source: Literal["gui", "cli"] = "gui"
    feature: str = Field(..., min_length=1, max_length=64)
    feature_id: str = Field(..., min_length=1, max_length=64)
    action: str = Field(default="run", max_length=32)
    status: Literal["success", "failed", "cancelled"]
    input: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    tool_version: Optional[str] = Field(default=None, max_length=32)


class ToolboxEventBatchCreate(BaseModel):
    events: List[ToolboxEventCreate] = Field(..., min_length=1, max_length=100)


class ToolboxEvent(ToolboxEventCreate):
    id: str = Field(..., alias="_id")
    server_time: datetime

    model_config = {"populate_by_name": True}


class ToolboxEventListResponse(BaseModel):
    items: List[ToolboxEvent]
    total: int
    skip: int
    limit: int


class ToolboxBatchInsertResult(BaseModel):
    inserted: int
    duplicates: int
    total: int


class ToolboxStatsResponse(BaseModel):
    total_events: int
    today_events: int
    success_count: int
    failed_count: int
    cancelled_count: int
    active_hostnames: int
    by_feature: List[Dict[str, Any]]
    daily_trend: List[Dict[str, Any]]
