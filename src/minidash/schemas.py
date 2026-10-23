"""Request and response models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class OrderStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    PLACED = "PLACED"
    PREPARING = "PREPARING"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class Restaurant(BaseModel):
    id: int
    name: str
    cuisine: str
    opens_at: str
    closes_at: str
    avg_prep_minutes: int


class MenuItem(BaseModel):
    id: int
    name: str
    price_cents: int


class OrderItemIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(gt=0, le=50)


class OrderIn(BaseModel):
    restaurant_id: int
    items: list[OrderItemIn] = Field(min_length=1)
    address: str = Field(min_length=1, max_length=300)
    scheduled_for: datetime | None = None


class OrderItemOut(BaseModel):
    menu_item_id: int
    name: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int


class OrderOut(BaseModel):
    id: int
    restaurant_id: int
    status: OrderStatus
    total_cents: int
    address: str
    created_at: str
    scheduled_for: str | None = None
    release_at: str | None = None
    released_at: str | None = None
    items: list[OrderItemOut]


class StatusUpdate(BaseModel):
    status: OrderStatus
