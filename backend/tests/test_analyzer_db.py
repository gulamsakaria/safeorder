import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app import state_machine as sm
from app.analyzer.case import load_case
from app.analyzer.pipeline import analyze
from app.enums import CourierStatus, DisputeStatus, FlagCode, Party, Route
from app.models import AnalysisResult, AuditLog, Dispute, EvidenceItem
from app.seed import seed_minimal
from tests.test_analyzer import FixedClassifier

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
CODE = "482913"


def add_dispute(
    session: Session, order_id: str, dispute_id: str, opened_at: datetime, claim: str
) -> Dispute:
    dispute = Dispute(
        id=dispute_id, order_id=order_id, opened_by=Party.BUYER, claim_text=claim,
        status=DisputeStatus.OPEN, opened_at=opened_at,
    )  # fmt: skip
    session.add(dispute)
    session.commit()
    return dispute


@pytest.fixture()
def db(session: Session) -> Session:
    seed_minimal(session)
    return session


def make_order(db: Session, placed: datetime):
    order = sm.place_order(
        db, buyer_id="B-0001", seller_id="S-0001", amount_bdt=2800,
        product_category="shoes", delivery_code=CODE, now=placed,
    )  # fmt: skip
    db.commit()
    return order


def test_full_path_from_database_rows(db: Session) -> None:
    order = make_order(db, NOW - timedelta(hours=50))
    sm.record_courier_event(db, order.id, CourierStatus.IN_TRANSIT, now=NOW - timedelta(hours=40))
    sm.record_courier_event(db, order.id, CourierStatus.DELIVERED, now=NOW - timedelta(hours=10))
    sm.confirm_delivery(db, order.id, CODE, now=NOW - timedelta(hours=10))
    db.commit()

    dispute = add_dispute(db, order.id, "D-0001", NOW, "I did not receive my parcel.")
    dispute.seller_response_text = "Delivered and the buyer confirmed with the code."
    dispute.seller_responded_at = NOW + timedelta(hours=2)
    db.add(dispute)
    db.add_all(
        [
            EvidenceItem(
                dispute_id="D-0001", party=Party.BUYER, created_at=NOW,
                description_text="Empty doorstep photo taken the same afternoon, nothing there.",
            ),
            EvidenceItem(
                dispute_id="D-0001", party=Party.SELLER, created_at=NOW,
                description_text="Courier tracking shows delivered and the code was entered.",
            ),
        ]
    )  # fmt: skip
    db.commit()

    case = load_case(db, "D-0001")
    assert case.courier_status == "delivered" and case.delivery_code_used
    assert case.delivered_at == NOW - timedelta(hours=10)
    assert [s for s, _ in case.courier_events] == ["in_transit", "delivered"]
    assert len(case.buyer_evidence) == 1 and len(case.seller_evidence) == 1
    assert case.buyer_disputes_in_window == 1

    result = analyze(db, "D-0001", FixedClassifier("BUYER_FALSE_CLAIM", 0.9))
    db.commit()
    assert result.flags == [FlagCode.CODE_CONTRADICTION]
    assert result.route == Route.HUMAN_REVIEW
    assert [e["event"] for e in result.timeline] == [
        "ORDER_PLACED_AND_HELD", "COURIER_IN_TRANSIT", "COURIER_DELIVERED",
        "DELIVERY_CODE_CONFIRMED", "BUYER_DISPUTE_FILED", "SELLER_RESPONDED",
    ]  # fmt: skip

    stored = db.exec(select(AnalysisResult)).one()
    assert stored.dispute_id == "D-0001"
    assert json.loads(stored.model_versions_json) == {
        "dispute": "fixed_test_v0",
        "rules": "rules_v1",
    }
    assert json.loads(stored.result_json)["route"] == "HUMAN_REVIEW"
    actions = [a.action for a in db.exec(select(AuditLog).where(AuditLog.entity_id == "D-0001"))]
    assert actions == ["DISPUTE_ANALYZED"]


def test_repeat_claimant_counts_only_disputes_inside_the_window(db: Session) -> None:
    opened = {
        "D-0001": NOW - timedelta(days=100),  # outside the 90 days
        "D-0002": NOW - timedelta(days=30),
        "D-0003": NOW - timedelta(days=10),
        "D-0004": NOW,
    }
    for dispute_id, when in opened.items():
        order = make_order(db, when - timedelta(hours=60))
        add_dispute(db, order.id, dispute_id, when, "Item arrived broken, see my photo.")
    assert load_case(db, "D-0004").buyer_disputes_in_window == 3  # D-0002, D-0003, D-0004
    assert load_case(db, "D-0003").buyer_disputes_in_window == 2
    assert load_case(db, "D-0001").buyer_disputes_in_window == 1

    result = analyze(db, "D-0004", FixedClassifier("SELLER_FAULT", 0.9), persist=False)
    assert FlagCode.REPEAT_CLAIMANT in result.flags
    assert result.flag_details[FlagCode.REPEAT_CLAIMANT] == {"count": 3, "days": 90}
    assert db.exec(select(AnalysisResult)).all() == []  # nothing saved when persist is off


def test_unknown_dispute_is_reported(db: Session) -> None:
    with pytest.raises(LookupError):
        analyze(db, "D-9999", FixedClassifier("SELLER_FAULT", 0.9))
