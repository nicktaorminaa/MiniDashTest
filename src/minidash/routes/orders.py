"""HTTP routes for orders."""

from fastapi import APIRouter

from minidash.routes.deps import ClockDep, Conn
from minidash.schemas import OrderIn, OrderOut, StatusUpdate
from minidash.services import ordering

router = APIRouter(tags=["orders"])


@router.post("/orders", response_model=OrderOut, status_code=201)
def place_order(order: OrderIn, conn: Conn, clock: ClockDep):
    return ordering.place_order(conn, order, clock.now())


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, conn: Conn):
    return ordering.get_order(conn, order_id)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_status(order_id: int, body: StatusUpdate, conn: Conn):
    return ordering.update_status(conn, order_id, body.status)
