"""HTTP routes for restaurants and menus."""

from fastapi import APIRouter

from minidash.routes.deps import Conn
from minidash.schemas import MenuItem, Restaurant
from minidash.services import menu as menu_service

router = APIRouter(tags=["restaurants"])


@router.get("/restaurants", response_model=list[Restaurant])
def list_restaurants(conn: Conn):
    return menu_service.list_restaurants(conn)


@router.get("/restaurants/{restaurant_id}/menu", response_model=list[MenuItem])
def get_menu(restaurant_id: int, conn: Conn):
    return menu_service.get_menu(conn, restaurant_id)
