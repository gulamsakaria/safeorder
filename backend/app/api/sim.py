"""Demo-only endpoints: courier events and the simulated clock."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import state_machine as sm
from app.api import common
from app.api.deps import get_session, require_demo
from app.clock import clock, to_iso
from app.models import Order
from app.schemas import AdvanceClockRequest, ClockOut, CourierEventRequest, OrderOut

router = APIRouter(prefix="/sim", tags=["demo"], dependencies=[Depends(require_demo)])


@router.post("/courier-event", response_model=OrderOut)
def courier_event(body: CourierEventRequest, session: Session = Depends(get_session)):
    if session.get(Order, body.order_id) is None:
        raise LookupError(f"order {body.order_id} not found")
    order = sm.record_courier_event(session, body.order_id, body.status)
    session.commit()
    return common.order_out(session, order)


@router.post("/advance-clock", response_model=ClockOut)
def advance_clock(body: AdvanceClockRequest, session: Session = Depends(get_session)):
    """Move the simulated clock forward and fire timers (hold expiry, missed dispatch)."""
    fired = sm.advance_clock(session, body.hours)
    session.commit()
    return {
        "now": to_iso(clock.now()),
        "fired": [{"order_id": oid, "event": event.value} for oid, event in fired],
    }
