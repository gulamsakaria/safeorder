"""Accounts, the sandbox wallet and wallet orders (buyer and seller sides)."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session, select

from app import accounts, auth, payments, rules, wallet
from app.api import common
from app.api.deps import get_classifier, get_config, get_optional_trust_model, get_session
from app.api.disputes import analyze_dispute, create_dispute
from app.api.errors import ApiError
from app.clock import clock
from app.db import write_audit
from app.disputes.classifier import ClassifierNotAvailable, DisputeClassifier
from app.enums import UserRole
from app.models import Order, Seller, User
from app.schemas import CreateDisputeRequest
from app.trust import service as trust_service
from app.trust.model import TrustModel
from app.wallet_schemas import (
    AddMoneyRequest,
    AuthOut,
    ChangePinRequest,
    ClaimRequest,
    LoginRequest,
    LookupOut,
    MeOut,
    MyOrderOut,
    PayOut,
    PayRequest,
    ProofImageOut,
    ProofRequest,
    RegisterRequest,
    ReportRequest,
    SellerModeRequest,
    WalletTxOut,
)

router = APIRouter(tags=["wallet"])


def me_out(user: User, cfg: dict[str, Any]) -> dict[str, Any]:
    left = max(0, cfg["wallet"]["add_money_total_cap_bdt"] - user.added_total_bdt)
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "role": user.role,
        "balance_bdt": user.balance_bdt,
        "held_bdt": user.held_bdt,
        "is_seller": user.seller_id is not None,
        "shop_name": user.shop_name,
        "shop_category": user.shop_category,
        "add_money_left_bdt": left,
    }


# ---- sign up and sign in ---------------------------------------------------------------------


@router.post("/auth/register", response_model=AuthOut, status_code=201)
def register(
    body: RegisterRequest,
    request: Request,
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Open a sandbox account with a phone number and a PIN. The welcome money is demo money."""
    if getattr(request.app.state, "starting", False):
        raise ApiError(503, "SERVICE_STARTING", "the service is starting, try again in a minute")
    user = accounts.create_user(session, phone=body.phone, name=body.name, pin=body.pin, cfg=cfg)
    session.commit()
    return {"token": auth.start_session(session, user, cfg), "user": me_out(user, cfg)}


@router.post("/auth/login", response_model=AuthOut)
def login(
    body: LoginRequest,
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    user = session.exec(select(User).where(User.phone == auth.normalize_phone(body.phone))).first()
    if user is None:
        # the same answer as a wrong PIN, so nobody can test which numbers have accounts
        raise ApiError(401, "WRONG_PIN", "the phone number or PIN is wrong")
    auth.check_pin(session, user, body.pin, cfg)
    if user.frozen:
        raise ApiError(403, "ACCOUNT_FROZEN", "this account is frozen by an admin")
    return {"token": auth.start_session(session, user, cfg), "user": me_out(user, cfg)}


@router.post("/auth/logout")
def logout(request: Request, session: Session = Depends(get_session)) -> dict[str, bool]:
    token = auth.bearer_token(request)
    if token:
        auth.end_session(session, token)
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(auth.current_user), cfg: dict[str, Any] = Depends(get_config)):
    return me_out(user, cfg)


@router.post("/me/seller-mode", response_model=MeOut)
def seller_mode(
    body: SellerModeRequest,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    accounts.enable_seller_mode(session, user, body.shop_name, body.category.strip().lower(), cfg)
    session.commit()
    return me_out(user, cfg)


@router.post("/me/pin", response_model=MeOut)
def change_pin(
    body: ChangePinRequest,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    auth.check_pin(session, user, body.old_pin, cfg)
    auth.validate_pin(body.new_pin, cfg)
    user.pin_hash = auth.hash_pin(body.new_pin)
    session.add(user)
    write_audit(session, f"user:{user.id}", "PIN_CHANGED", "user", user.id, "{}", clock.now())
    session.commit()
    return me_out(user, cfg)


# ---- wallet ----------------------------------------------------------------------------------


@router.post("/wallet/add-money", response_model=MeOut)
def add_money(
    body: AddMoneyRequest,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Take sandbox money (no real payment). Limited per request and per account."""
    payments.add_money(session, user, body.amount_bdt, cfg)
    session.commit()
    return me_out(user, cfg)


@router.get("/wallet/history", response_model=list[WalletTxOut])
def wallet_history(
    user: User = Depends(auth.current_user), session: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    # a seller must not learn an order number from the history before entering it
    hidden = {o.id for o in payments.my_orders(session, user, "SELLER") if o.claimed_at is None}
    rows = []
    for tx in wallet.history(session, user):
        row = tx.model_dump()
        if tx.order_id in hidden:
            row["order_id"] = None
        rows.append(row)
    return rows


@router.get("/wallet/lookup", response_model=LookupOut)
def lookup(
    phone: str = Query(min_length=1, max_length=20),
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    model: TrustModel | None = Depends(get_optional_trust_model),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Who owns this number? For a seller this also runs the Trust Check, before any payment."""
    target = session.exec(select(User).where(User.phone == auth.normalize_phone(phone))).first()
    if target is None or target.frozen:
        raise ApiError(404, "NOT_FOUND", "no account has this phone number")
    out: dict[str, Any] = {
        "phone": target.phone,
        "name": target.shop_name or target.name if target.seller_id else target.name,
        "is_seller": target.seller_id is not None,
        "shop_name": target.shop_name,
        "is_self": target.id == user.id,
        "trust": None,
        "requires_extra_confirmation": False,
    }
    if target.seller_id and model is not None:
        accounts.refresh_seller_features(session, target.seller_id)
        try:
            result = trust_service.check_seller(session, model, seller_id=target.seller_id, cfg=cfg)
            trust_service.ensure_initial_snapshot(session, model, target.seller_id, cfg)
            extra = rules.requires_extra_confirmation(result.band, cfg)
            out["trust"] = {**result.to_api(), "requires_extra_confirmation": extra}
            out["requires_extra_confirmation"] = extra
        except trust_service.FeaturesMissing:
            pass
        session.commit()
    return out


@router.post("/wallet/pay", response_model=PayOut)
def pay(
    body: PayRequest,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    model: TrustModel | None = Depends(get_optional_trust_model),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Send money or pay a seller. Paying a seller account holds the money until the buyer
    confirms delivery, an admin decides, or the proof rules release it."""
    auth.check_pin(session, user, body.pin, cfg)
    result = payments.pay(
        session,
        user,
        to_phone=auth.normalize_phone(body.to_phone),
        amount=body.amount_bdt,
        order_ref=body.order_ref,
        model=model,
        confirm_risk=body.confirm_risk,
        cfg=cfg,
    )
    session.commit()
    order = result["order"]
    to: User = result["to"]
    return {
        "kind": result["kind"],
        "amount_bdt": body.amount_bdt,
        "to_name": to.shop_name or to.name,
        "to_phone": to.phone,
        "order": payments.order_view(session, order, "BUYER", cfg) if order else None,
        "me": me_out(user, cfg),
    }


# ---- wallet orders ---------------------------------------------------------------------------


@router.get("/my/orders", response_model=list[MyOrderOut])
def my_orders(
    role: str = Query(default="BUYER", pattern="^(BUYER|SELLER)$"),
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> list[dict[str, Any]]:
    return [
        payments.order_view(session, o, role, cfg) for o in payments.my_orders(session, user, role)
    ]


@router.get("/my/orders/{order_id}", response_model=MyOrderOut)
def my_order(
    order_id: str,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    order, role = payments.load_order_for(session, user, order_id)
    return payments.order_view(session, order, role, cfg)


@router.get("/my/orders/{order_id}/proof-image", response_model=ProofImageOut)
def proof_image(
    order_id: str,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    order, _ = payments.load_order_for(session, user, order_id)
    return {"image": order.proof_image}


@router.post("/my/orders/{order_id}/accept", response_model=MyOrderOut)
def accept(
    order_id: str,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """The buyer says the delivery arrived: the held money goes to the seller."""
    order = payments.buyer_accept(session, user, order_id)
    session.commit()
    return payments.order_view(session, order, "BUYER", cfg)


@router.post("/my/orders/{order_id}/report", status_code=201)
def report_problem(
    order_id: str,
    body: ReportRequest,
    user: User = Depends(auth.current_user),
    session: Session = Depends(get_session),
    classifier: DisputeClassifier = Depends(get_classifier),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """The buyer reports a problem. The AI analyzer runs at once; an admin decides."""
    order, role = payments.load_order_for(session, user, order_id)
    if role != "BUYER":
        raise ApiError(403, "FORBIDDEN", "only the buyer can report a problem")
    dispute = create_dispute(
        CreateDisputeRequest(
            order_id=order.id,
            claim_text=body.claim_text,
            evidence_text=body.evidence_text,
            claim_type=body.claim_type,
        ),
        session,
        cfg,
        user,
    )
    try:
        analyze_dispute(dispute["id"], session, classifier, cfg, user)
    except ClassifierNotAvailable:
        pass  # the report stands; the admin can run the analysis later
    return {"dispute": dispute, "order": payments.order_view(session, order, "BUYER", cfg)}


@router.post("/seller/claim", response_model=MyOrderOut)
def claim(
    body: ClaimRequest,
    user: User = Depends(auth.current_seller),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """The seller types the order number that the buyer gave, and so takes the payment in."""
    order = payments.claim_order(session, user, body.order_no)
    session.commit()
    return payments.order_view(session, order, "SELLER", cfg)


@router.post("/my/orders/{order_id}/proof", response_model=MyOrderOut)
def submit_proof(
    order_id: str,
    body: ProofRequest,
    user: User = Depends(auth.current_seller),
    session: Session = Depends(get_session),
    model: TrustModel | None = Depends(get_optional_trust_model),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """The seller shows delivery proof (tracking number, photo of the receipt)."""
    order = payments.submit_proof(
        session, user, order_id,
        tracking_no=body.tracking_no, note=body.note, image=body.image, model=model, cfg=cfg,
    )  # fmt: skip
    session.commit()
    return payments.order_view(session, order, "SELLER", cfg)


def is_admin(user: User | None) -> bool:
    return user is not None and user.role == UserRole.ADMIN


__all__ = ["router", "me_out", "is_admin", "Order", "Seller", "common"]
