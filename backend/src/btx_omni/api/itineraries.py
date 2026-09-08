from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from btx_omni.api.accounts import get_runtime
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal
from btx_omni.persistence.itineraries import ItineraryConflict

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


class ItineraryStopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=160)
    account_id: str = Field(min_length=1, max_length=100)
    facility_id: str = Field(min_length=1, max_length=120)
    site_name: str = Field(min_length=1, max_length=300)
    latitude: str = Field(max_length=32)
    longitude: str = Field(max_length=32)
    purpose: str = Field(default="", max_length=500)
    contact_name: str = Field(default="", max_length=300)
    meeting_status: Literal["NOT_REQUESTED", "PROPOSED", "CONFIRMED", "CANCELED"] = "NOT_REQUESTED"
    visit_brief: str = Field(default="", max_length=2000)
    travel_distance_miles: float | None = Field(default=None, ge=0)
    travel_duration_minutes: int | None = Field(default=None, ge=0)
    route_provider: Literal["GOOGLE_MAPS_ROUTES"] | None = None
    route_retrieved_at: datetime | None = None

    @field_validator("latitude")
    @classmethod
    def latitude_valid(cls, value: str) -> str:
        if not -90 <= float(value) <= 90:
            raise ValueError("Latitude is out of range.")
        return value

    @field_validator("longitude")
    @classmethod
    def longitude_valid(cls, value: str) -> str:
        if not -180 <= float(value) <= 180:
            raise ValueError("Longitude is out of range.")
        return value


class SaveItinerary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    origin_label: str = Field(default="", max_length=300)
    origin_latitude: str | None = Field(default=None, max_length=32)
    origin_longitude: str | None = Field(default=None, max_length=32)
    stops: tuple[ItineraryStopInput, ...] = Field(max_length=20)
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")

    @field_validator("stops")
    @classmethod
    def distinct_stops(cls, value: tuple[ItineraryStopInput, ...]):
        if len({item.id for item in value}) != len(value):
            raise ValueError("Itinerary stop IDs must be distinct.")
        return value

    @model_validator(mode="after")
    def complete_origin(self):
        if (self.origin_latitude is None) != (self.origin_longitude is None):
            raise ValueError("Origin latitude and longitude must be supplied together.")
        if self.origin_latitude is not None:
            if not -90 <= float(self.origin_latitude) <= 90:
                raise ValueError("Origin latitude is out of range.")
            if not -180 <= float(self.origin_longitude) <= 180:
                raise ValueError("Origin longitude is out of range.")
        return self


@router.get("/current")
def current_itinerary(runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    return {"itinerary": runtime.itineraries.get(current.user_id)}


@router.post("/current")
def save_itinerary(body: SaveItinerary, runtime: PocRuntime = Depends(get_runtime), current: Principal = Depends(principal)):
    sample = runtime.environment()
    facilities = {(item.account_id, item.id): item for item in sample.facilities}
    for stop in body.stops:
        facility = facilities.get((stop.account_id, stop.facility_id))
        if facility is None or facility.latitude is None or facility.longitude is None:
            raise HTTPException(422, f"Itinerary stop {stop.id} is not a canonical verified account site.")
        if float(stop.latitude) != float(facility.latitude) or float(stop.longitude) != float(facility.longitude):
            raise HTTPException(422, f"Itinerary stop {stop.id} coordinates do not match the canonical site.")
    payload = body.model_dump(exclude={"title", "expected_version", "idempotency_key"}, mode="json")
    try:
        return runtime.itineraries.save(
            user_id=current.user_id,
            title=body.title.strip(),
            payload=payload,
            idempotency_key=body.idempotency_key,
            expected_version=body.expected_version,
            now=datetime.now(UTC),
        )
    except ItineraryConflict as error:
        raise HTTPException(409, str(error)) from error
