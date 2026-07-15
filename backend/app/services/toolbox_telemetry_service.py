from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.databases.mongodb import get_toolbox_events_collection
from app.models.toolbox_telemetry_model import (
    ToolboxEvent,
    ToolboxEventCreate,
    ToolboxStatsResponse,
)
from app.services.user_service import MongoRepository

COLLECTION_NAME = "toolbox_events"
CLIENT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_client_time(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, CLIENT_TIME_FORMAT)
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


class ToolboxTelemetryService(MongoRepository):
    def __init__(self):
        self.collection = get_toolbox_events_collection()

    @staticmethod
    def _to_event_document(event: ToolboxEventCreate) -> dict:
        doc = event.model_dump()
        doc["client_time_dt"] = parse_client_time(event.client_time)
        doc["server_time"] = datetime.now(timezone.utc)
        return doc

    async def insert_event(self, event: ToolboxEventCreate) -> tuple[bool, Optional[ToolboxEvent]]:
        existing = await self.collection.find_one({"event_id": event.event_id})
        if existing:
            return False, self.to_model(existing, ToolboxEvent)

        doc = self._to_event_document(event)
        result = await self.collection.insert_one(doc)
        created = await self.collection.find_one({"_id": result.inserted_id})
        return True, self.to_model(created, ToolboxEvent)

    async def insert_batch(self, events: List[ToolboxEventCreate]) -> Dict[str, int]:
        if not events:
            return {"inserted": 0, "duplicates": 0, "total": 0}

        event_ids = [event.event_id for event in events]
        existing_docs = await self.collection.find(
            {"event_id": {"$in": event_ids}},
            {"event_id": 1},
        ).to_list(length=len(event_ids))
        existing_ids = {doc["event_id"] for doc in existing_docs}

        docs = []
        for event in events:
            if event.event_id in existing_ids:
                continue
            docs.append(self._to_event_document(event))

        inserted = 0
        if docs:
            result = await self.collection.insert_many(docs, ordered=False)
            inserted = len(result.inserted_ids)

        return {
            "inserted": inserted,
            "duplicates": len(events) - inserted,
            "total": len(events),
        }

    def _build_query(
        self,
        hostname: Optional[str] = None,
        feature_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        error_keyword: Optional[str] = None,
    ) -> dict:
        query: dict = {}
        if hostname:
            query["hostname"] = hostname
        if feature_id:
            query["feature_id"] = feature_id
        if status:
            query["status"] = status
        if error_keyword:
            query["error"] = {"$regex": error_keyword, "$options": "i"}

        time_filter: dict = {}
        if start_time:
            time_filter["$gte"] = parse_client_time(start_time)
        if end_time:
            time_filter["$lte"] = parse_client_time(end_time)
        if time_filter:
            query["client_time_dt"] = time_filter
        return query

    async def query_events(
        self,
        skip: int = 0,
        limit: int = 50,
        hostname: Optional[str] = None,
        feature_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        error_keyword: Optional[str] = None,
    ) -> tuple[List[ToolboxEvent], int]:
        query = self._build_query(
            hostname=hostname,
            feature_id=feature_id,
            status=status,
            start_time=start_time,
            end_time=end_time,
            error_keyword=error_keyword,
        )
        total = await self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort([("client_time_dt", -1), ("server_time", -1)])
            .skip(skip)
            .limit(limit)
        )
        items = []
        async for doc in cursor:
            items.append(self.to_model(doc, ToolboxEvent))
        return items, total

    async def get_event_by_id(self, event_id: str) -> Optional[ToolboxEvent]:
        doc = await self.collection.find_one({"event_id": event_id})
        return self.to_model(doc, ToolboxEvent)

    async def get_hostnames(self) -> List[str]:
        values = await self.collection.distinct("hostname")
        return sorted(value for value in values if value)

    async def get_stats(
        self,
        days: int = 30,
        hostname: Optional[str] = None,
        feature_id: Optional[str] = None,
    ) -> ToolboxStatsResponse:
        days = max(1, min(days, 180))
        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(days=days)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        match: dict = {"client_time_dt": {"$gte": start_dt}}
        if hostname:
            match["hostname"] = hostname
        if feature_id:
            match["feature_id"] = feature_id

        pipeline = [
            {"$match": match},
            {
                "$facet": {
                    "totals": [
                        {
                            "$group": {
                                "_id": None,
                                "total_events": {"$sum": 1},
                                "success_count": {
                                    "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                                },
                                "failed_count": {
                                    "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                                },
                                "cancelled_count": {
                                    "$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}
                                },
                                "hostnames": {"$addToSet": "$hostname"},
                            }
                        }
                    ],
                    "today": [
                        {"$match": {"client_time_dt": {"$gte": today_start}}},
                        {"$count": "count"},
                    ],
                    "by_feature": [
                        {
                            "$group": {
                                "_id": {"feature_id": "$feature_id", "feature": "$feature"},
                                "count": {"$sum": 1},
                                "success_count": {
                                    "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                                },
                                "failed_count": {
                                    "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                                },
                            }
                        },
                        {"$sort": {"count": -1}},
                    ],
                    "daily_trend": [
                        {
                            "$group": {
                                "_id": {
                                    "$dateToString": {
                                        "format": "%Y-%m-%d",
                                        "date": "$client_time_dt",
                                    }
                                },
                                "count": {"$sum": 1},
                            }
                        },
                        {"$sort": {"_id": 1}},
                    ],
                }
            },
        ]

        result = await self.collection.aggregate(pipeline).to_list(length=1)
        facet = result[0] if result else {}

        totals = facet.get("totals", [{}])[0] if facet.get("totals") else {}
        today = facet.get("today", [{}])[0] if facet.get("today") else {}

        by_feature = []
        for item in facet.get("by_feature", []):
            feature_info = item.get("_id", {})
            count = item.get("count", 0)
            success_count = item.get("success_count", 0)
            by_feature.append(
                {
                    "feature_id": feature_info.get("feature_id", ""),
                    "feature": feature_info.get("feature", ""),
                    "count": count,
                    "success_count": success_count,
                    "failed_count": item.get("failed_count", 0),
                    "success_rate": round(success_count / count * 100, 1) if count else 0,
                }
            )

        daily_trend = [
            {"date": item["_id"], "count": item["count"]}
            for item in facet.get("daily_trend", [])
        ]

        hostnames = totals.get("hostnames", [])
        return ToolboxStatsResponse(
            total_events=totals.get("total_events", 0),
            today_events=today.get("count", 0),
            success_count=totals.get("success_count", 0),
            failed_count=totals.get("failed_count", 0),
            cancelled_count=totals.get("cancelled_count", 0),
            active_hostnames=len(hostnames),
            by_feature=by_feature,
            daily_trend=daily_trend,
        )


async def ensure_toolbox_events_indexes():
    collection = get_toolbox_events_collection()
    await collection.create_index("event_id", unique=True)
    await collection.create_index([("hostname", 1), ("client_time_dt", -1)])
    await collection.create_index([("feature_id", 1), ("status", 1), ("client_time_dt", -1)])
    await collection.create_index([("server_time", -1)])
    logger.info(f"MongoDB indexes ensured for collection: {COLLECTION_NAME}")
