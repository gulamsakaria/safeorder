from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import state_machine as sm
from app.api import common
from app.api.deps import get_config, get_session
from app.models import Order
from app.schemas import ConfirmDeliveryRequest, CreateOrderRequest, OrderOut

router = APIRouter(tags=["orders"])


def _get_order(session: Session, order_id: str) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise LookupError(f"order {order_id} not found")
    return order


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(
    body: CreateOrderRequest,
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Create a Safe Order and hold the money (simulated). The sandbox code is returned once."""
    order = sm.place_order(
        session,
        buyer_id=body.buyer_id,
        seller_id=body.seller_id,
        amount_bdt=body.amount_bdt,
        product_category=body.product_category,
        delivery_code=lambda order_id: common.delivery_code_for(order_id, cfg),
    )
    session.commit()
    return common.order_out(session, order, common.delivery_code_for(order.id, cfg))


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    return common.order_out(session, _get_order(session, order_id))


@router.post("/orders/{order_id}/confirm-delivery", response_model=OrderOut)
def confirm_delivery(
    order_id: str, body: ConfirmDeliveryRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """The buyer confirms with the delivery code. A wrong code changes nothing."""
    _get_order(session, order_id)
    try:
        order = sm.confirm_delivery(session, order_id, body.code)
    except sm.InvalidDeliveryCode:
        session.commit()  # keep the audit row of the rejected attempt
        raise
    session.commit()
    return common.order_out(session, order)
