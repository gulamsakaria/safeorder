"""Accounts, the sandbox wallet, held payments, claiming, proof and the admin area."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.clock import clock
from app.db import create_db, make_engine
from app.main import create_app
from app.models import AuditLog, Seller, User
from app.trust.model import TrustModel
from tests.test_analyzer import FixedClassifier
from tests.test_api import REPO

PIN = "12345"
BUYER = "01711111111"
SELLER = "01822222222"
ADMIN = "01933333333"
IMAGE = "data:image/png;base64," + "A" * 400


@pytest.fixture(scope="module")
def trust_model() -> TrustModel:
    return TrustModel.load(REPO / "models" / "trust_v1.joblib")


class World:
    def __init__(self, engine, app) -> None:
        self.engine = engine
        self.client = TestClient(app, raise_server_exceptions=False)
        self.tokens: dict[str, str] = {}

    def call(self, method: str, path: str, who: str | None = None, expect: int | None = None, **kw):
        headers = {"Authorization": f"Bearer {self.tokens[who]}"} if who else {}
        response = self.client.request(method, f"/api{path}", headers=headers, **kw)
        if expect is not None:
            assert response.status_code == expect, (path, response.status_code, response.text)
        return response

    def post(self, path, body=None, who=None, expect=None):
        return self.call("POST", path, who, expect, json=body or {})

    def get(self, path, who=None, expect=None):
        return self.call("GET", path, who, expect)

    def register(self, who: str, phone: str, name: str) -> dict:
        out = self.post("/auth/register", {"name": name, "phone": phone, "pin": PIN}, expect=201)
        self.tokens[who] = out.json()["token"]
        return out.json()["user"]

    def make_admin(self, phone: str = ADMIN) -> None:
        self.register("admin", phone, "Admin")
        with Session(self.engine) as s:
            user = s.exec(select(User).where(User.phone == phone)).one()
            user.role = "ADMIN"
            s.add(user)
            s.commit()

    def me(self, who: str) -> dict:
        return self.get("/me", who, 200).json()

    def pay(self, who, to, amount, ref=None, expect=200, **extra):
        body = {"to_phone": to, "amount_bdt": amount, "pin": PIN, "order_ref": ref, **extra}
        return self.post("/wallet/pay", body, who, expect)

    def seller_mode(self, who="seller"):
        return self.post("/me/seller-mode", {"shop_name": "Rina Fashion", "category": "clothing"},
                         who, 200)  # fmt: skip


@pytest.fixture()
def world(tmp_path, trust_model):
    clock.reset()
    engine = make_engine(f"sqlite:///{tmp_path / 'wallet.db'}")
    create_db(engine)
    classifier = FixedClassifier("SELLER_FAULT", 0.9)
    app = create_app(engine=engine, trust_model=trust_model, classifier=classifier)
    w = World(engine, app)
    w.register("buyer", BUYER, "Karim Buyer")
    w.register("seller", SELLER, "Rina Seller")
    w.seller_mode()
    yield w
    clock.reset()


def held_order(world: World, amount: int = 500, ref: str | None = "MY-1") -> dict:
    return world.pay("buyer", SELLER, amount, ref).json()["order"]


# ---- accounts ----------------------------------------------------------------------------


def test_register_gives_sandbox_money_and_login_works(world: World) -> None:
    assert world.me("buyer")["balance_bdt"] == 2000
    out = world.post("/auth/login", {"phone": BUYER, "pin": PIN}, expect=200).json()
    assert out["user"]["phone"] == BUYER and out["token"]


def test_phone_and_pin_are_validated_and_unique(world: World) -> None:
    world.post("/auth/register", {"name": "X Y", "phone": "12345", "pin": PIN}, expect=422)
    world.post("/auth/register", {"name": "X Y", "phone": "01744444444", "pin": "12"}, expect=422)
    world.post("/auth/register", {"name": "Dup", "phone": BUYER, "pin": PIN}, expect=409)
    plus = {"name": "Plus", "phone": "+8801755555555", "pin": PIN}
    world.post("/auth/register", plus, expect=201)


def test_wrong_pin_locks_the_account_without_revealing_which_numbers_exist(world: World) -> None:
    unknown = world.post("/auth/login", {"phone": "01999999999", "pin": PIN}, expect=401)
    wrong = world.post("/auth/login", {"phone": BUYER, "pin": "00000"}, expect=401)
    assert unknown.json() == wrong.json()
    for _ in range(4):
        world.post("/auth/login", {"phone": BUYER, "pin": "00000"}, expect=401)
    world.post("/auth/login", {"phone": BUYER, "pin": PIN}, expect=429)


def test_pin_is_stored_hashed_and_tokens_only_as_hashes(world: World) -> None:
    with Session(world.engine) as s:
        user = s.exec(select(User).where(User.phone == BUYER)).one()
        assert PIN not in user.pin_hash and user.pin_hash.startswith("scrypt$")
    assert world.get("/me", None, 401).json()["error"]["code"] == "NOT_SIGNED_IN"
    world.post("/auth/logout", None, "buyer", 200)
    assert world.get("/me", "buyer", 401)


def test_add_money_has_limits(world: World) -> None:
    world.post("/wallet/add-money", {"amount_bdt": 5000}, "buyer", 200)
    assert world.me("buyer")["balance_bdt"] == 7000
    world.post("/wallet/add-money", {"amount_bdt": 5001}, "buyer", 422)
    for _ in range(3):
        world.post("/wallet/add-money", {"amount_bdt": 5000}, "buyer", 200)
    world.post("/wallet/add-money", {"amount_bdt": 1}, "buyer", 409)  # the 20,000 cap is used up


# ---- paying ------------------------------------------------------------------------------


def test_lookup_shows_the_seller_trust_check_before_paying(world: World) -> None:
    out = world.get(f"/wallet/lookup?phone={SELLER}", "buyer", 200).json()
    assert out["is_seller"] and out["name"] == "Rina Fashion"
    assert out["trust"]["band"] == "LIMITED_HISTORY"  # a brand-new seller
    own = world.get(f"/wallet/lookup?phone={BUYER}", "buyer", 200).json()
    assert own["is_self"] and not own["is_seller"]
    world.get("/wallet/lookup?phone=01999999999", "buyer", 404)


def test_send_money_to_a_normal_account_arrives_at_once(world: World) -> None:
    world.register("friend", "01766666666", "Friend")
    out = world.pay("buyer", "01766666666", 300).json()
    assert out["kind"] == "SENT" and out["order"] is None
    assert world.me("buyer")["balance_bdt"] == 1700
    assert world.me("friend")["balance_bdt"] == 2300


def test_paying_a_seller_holds_the_money(world: World) -> None:
    order = held_order(world, 500, "MY-1")
    assert order["status"] == "HELD" and order["id"].startswith("O-")
    assert world.me("buyer")["balance_bdt"] == 1500
    seller = world.me("seller")
    assert seller["held_bdt"] == 500 and seller["balance_bdt"] == 2000


def test_payment_rules(world: World) -> None:
    world.pay("buyer", BUYER, 100, expect=422)  # yourself
    world.pay("buyer", "01999999999", 100, expect=404)
    world.pay("buyer", SELLER, 5000, expect=409)  # not enough balance
    bad = world.post("/wallet/pay", {"to_phone": SELLER, "amount_bdt": 100, "pin": "99999"},
                     "buyer", 401)  # fmt: skip
    assert bad.json()["error"]["code"] == "WRONG_PIN"
    assert world.me("buyer")["balance_bdt"] == 2000


def test_a_seller_sees_the_payment_but_not_its_order_number_until_claiming(world: World) -> None:
    order = held_order(world, 500, "MY-1")
    rows = world.get("/my/orders?role=SELLER", "seller", 200).json()
    assert len(rows) == 1 and rows[0]["id"] == "UNCLAIMED" and rows[0]["order_ref"] is None
    assert rows[0]["buyer_phone"].startswith("017") and "****" in rows[0]["buyer_phone"]
    history = world.get("/wallet/history", "seller", 200).json()
    assert all(row["order_id"] is None for row in history)  # still unknown to the seller
    world.post("/seller/claim", {"order_no": "WRONG"}, "seller", 404)
    # the buyer's own reference, in other letters
    claimed = world.post("/seller/claim", {"order_no": "my-1"}, "seller", 200).json()
    assert claimed["id"] == order["id"] and claimed["claimed_at"]
    world.post("/seller/claim", {"order_no": order["id"]}, "seller", 404)  # already claimed


def test_claim_by_the_system_order_number(world: World) -> None:
    order = held_order(world, 500, None)
    claimed = world.post("/seller/claim", {"order_no": order["id"]}, "seller", 200).json()
    assert claimed["id"] == order["id"]


def test_only_sellers_can_claim(world: World) -> None:
    world.post("/seller/claim", {"order_no": "O-0001"}, "buyer", 403)


# ---- delivery, refunds, proof ------------------------------------------------------------


def test_buyer_accepting_pays_the_seller(world: World) -> None:
    order = held_order(world, 500)
    world.post("/seller/claim", {"order_no": order["id"]}, "seller", 200)
    done = world.post(f"/my/orders/{order['id']}/accept", None, "buyer", 200).json()
    assert done["status"] == "RELEASED"
    seller = world.me("seller")
    assert seller["balance_bdt"] == 2500 and seller["held_bdt"] == 0
    kinds = [t["kind"] for t in world.get("/wallet/history", "seller", 200).json()]
    assert kinds[:2] == ["RELEASED", "PAYMENT_RECEIVED_HELD"]
    world.post(f"/my/orders/{order['id']}/accept", None, "buyer", 409)  # only once


def test_only_the_buyer_can_accept_and_strangers_see_nothing(world: World) -> None:
    order = held_order(world)
    world.register("other", "01777777777", "Other")
    world.post(f"/my/orders/{order['id']}/accept", None, "seller", 403)
    world.get(f"/my/orders/{order['id']}", "other", 404)
    world.get(f"/orders/{order['id']}", "other", 403)
    world.get(f"/orders/{order['id']}", None, 401)
    world.get(f"/orders/{order['id']}", "buyer", 200)


def test_unclaimed_payment_goes_back_after_the_deadline(world: World) -> None:
    order = held_order(world, 500)
    world.make_admin()
    world.post("/admin/advance-clock", {"hours": 23}, "admin", 200)
    assert world.get(f"/my/orders/{order['id']}", "buyer", 200).json()["status"] == "HELD"
    fired = world.post("/admin/advance-clock", {"hours": 2}, "admin", 200).json()["fired"]
    assert fired == [{"order_id": order["id"], "event": "SELLER_NO_CLAIM"}]
    assert world.me("buyer")["balance_bdt"] == 2000
    assert world.me("seller")["held_bdt"] == 0


def test_buyer_report_runs_the_ai_analysis_and_an_admin_decides(world: World) -> None:
    order = held_order(world, 800)
    world.post("/seller/claim", {"order_no": order["id"]}, "seller", 200)
    out = world.post(f"/my/orders/{order['id']}/report",
                     {"claim_text": "The parcel never arrived, the courier did not call me."},
                     "buyer", 201).json()  # fmt: skip
    dispute_id = out["dispute"]["id"]
    assert out["order"]["status"] == "DISPUTED"
    world.make_admin()
    case = world.get(f"/analyst/disputes/{dispute_id}", "admin", 200).json()
    assert case["analysis"]["recommendation"]
    assert world.me("seller")["held_bdt"] == 800  # nothing moves until a person decides
    world.post(f"/analyst/disputes/{dispute_id}/decision",
               {"decision": "REFUND_BUYER", "note": "No courier proof.", "analyst_id": "admin"},
               "admin", 200)  # fmt: skip
    assert world.me("buyer")["balance_bdt"] == 2000
    assert world.me("seller")["held_bdt"] == 0


def test_disputes_of_wallet_orders_are_private(world: World) -> None:
    order = held_order(world)
    world.post("/seller/claim", {"order_no": order["id"]}, "seller", 200)
    out = world.post(f"/my/orders/{order['id']}/report", {"claim_text": "Wrong item sent."},
                     "buyer", 201).json()  # fmt: skip
    did = out["dispute"]["id"]
    world.register("other", "01777777777", "Other")
    world.get(f"/disputes/{did}", "other", 403)
    world.get(f"/disputes/{did}", None, 401)
    world.post(f"/disputes/{did}/seller-response", {"response_text": "I sent the right item."},
               "buyer", 403)  # fmt: skip
    world.post(f"/disputes/{did}/seller-response", {"response_text": "I sent the right item."},
               "seller", 200)  # fmt: skip


def proof(world: World, order_id: str, tracking="SA123456789", image=IMAGE, expect=200):
    body = {"tracking_no": tracking, "note": "Handed to the courier", "image": image}
    return world.post(f"/my/orders/{order_id}/proof", body, "seller", expect)


def claimed_order(world: World, amount: int = 500) -> dict:
    order = held_order(world, amount)
    world.post("/seller/claim", {"order_no": order["id"]}, "seller", 200)
    return order


def test_clean_proof_pays_the_seller_after_the_buyer_stays_silent(world: World) -> None:
    order = claimed_order(world)
    out = proof(world, order["id"]).json()
    assert out["proof"]["flags"] == [] and out["silence_deadline"]
    world.make_admin()
    world.post("/admin/advance-clock", {"hours": 71}, "admin", 200)
    assert world.get(f"/my/orders/{order['id']}", "buyer", 200).json()["status"] == "HELD"
    fired = world.post("/admin/advance-clock", {"hours": 2}, "admin", 200).json()["fired"]
    assert fired == [{"order_id": order["id"], "event": "PROOF_RELEASE"}]
    assert world.me("seller")["balance_bdt"] == 2500


def test_proof_needs_a_claim_and_a_real_photo(world: World) -> None:
    order = held_order(world)
    proof(world, order["id"], expect=409)  # the seller has not entered the number yet
    world.post("/seller/claim", {"order_no": order["id"]}, "seller", 200)
    proof(world, order["id"], image="not an image", expect=422)
    proof(world, order["id"], image="data:image/png;base64," + "A" * 400_001, expect=422)


def test_suspicious_proof_waits_for_an_admin_and_never_releases_by_itself(world: World) -> None:
    first = claimed_order(world, 300)
    proof(world, first["id"], tracking="DUP-TRACK-1")
    second = claimed_order(world, 400)
    flagged = proof(world, second["id"], tracking="dup-track-1").json()  # same number, same photo
    assert {"DUPLICATE_TRACKING", "DUPLICATE_IMAGE"} <= set(flagged["proof"]["flags"])
    world.make_admin()
    world.post("/admin/advance-clock", {"hours": 100}, "admin", 200)
    assert world.get(f"/my/orders/{second['id']}", "buyer", 200).json()["status"] == "HELD"
    rows = world.get("/admin/orders?only_open=true", "admin", 200).json()
    assert [r["id"] for r in rows if r["needs_decision"]] == [second["id"]]
    world.post(f"/admin/orders/{second['id']}/decision",
               {"decision": "REFUND_TO_BUYER", "note": "Same receipt used twice."},
               "admin", 200)  # fmt: skip
    assert world.get(f"/my/orders/{second['id']}", "buyer", 200).json()["status"] == "REFUNDED"
    image = world.get(f"/admin/orders/{second['id']}/proof-image", "admin", 200).json()["image"]
    assert image == IMAGE


def test_bad_tracking_format_is_flagged(world: World) -> None:
    order = claimed_order(world)
    out = proof(world, order["id"], tracking="12").json()
    assert "BAD_TRACKING_FORMAT" in out["proof"]["flags"]


# ---- admin -------------------------------------------------------------------------------


def test_admin_area_is_for_admins_only(world: World) -> None:
    world.get("/admin/overview", "buyer", 403)
    world.get("/admin/users", None, 401)
    world.make_admin()
    overview = world.get("/admin/overview", "admin", 200).json()
    assert overview["users"] == 3 and overview["sellers"] == 1
    users = world.get("/admin/users", "admin", 200).json()
    buyer_id = next(u["id"] for u in users if u["phone"] == BUYER)
    world.post(f"/admin/users/{buyer_id}/freeze", {"frozen": True}, "admin", 200)
    world.get("/me", "buyer", 403)
    world.post("/auth/login", {"phone": BUYER, "pin": PIN}, expect=403)
    world.post(f"/admin/users/{buyer_id}/freeze", {"frozen": False}, "admin", 200)
    world.post(f"/admin/users/{buyer_id}/grant", {"amount_bdt": 1000}, "admin", 200)
    assert world.me("buyer")["balance_bdt"] == 3000


def test_the_admin_account_cannot_be_frozen(world: World) -> None:
    world.make_admin()
    users = world.get("/admin/users", "admin", 200).json()
    admin_id = next(u["id"] for u in users if u["role"] == "ADMIN")
    world.post(f"/admin/users/{admin_id}/freeze", {"frozen": True}, "admin", 409)


def test_wallet_accounts_cannot_be_used_through_the_classic_order_api(world: World) -> None:
    with Session(world.engine) as s:
        buyer_id = s.exec(select(User).where(User.phone == BUYER)).one().buyer_id
        seller_id = s.exec(select(Seller)).first().id
    world.post("/orders", {"buyer_id": buyer_id, "seller_id": seller_id, "amount_bdt": 100,
                           "product_category": "shoes"}, None, 403)  # fmt: skip


def test_money_never_appears_or_disappears(world: World) -> None:
    order = claimed_order(world, 700)
    world.post(f"/my/orders/{order['id']}/accept", None, "buyer", 200)
    world.pay("buyer", SELLER, 100)  # a second, unclaimed payment is still held
    with Session(world.engine) as s:
        users = s.exec(select(User)).all()
        assert sum(u.balance_bdt + u.held_bdt for u in users) == 4000  # two bonuses of 2000
        assert s.exec(select(AuditLog)).all()


def test_protected_admin_mode_closes_the_analyst_console(tmp_path, trust_model) -> None:
    clock.reset()
    engine = make_engine(f"sqlite:///{tmp_path / 'p.db'}")
    create_db(engine)
    from app.config import load_config
    from app.deploy import apply_env

    cfg = apply_env(load_config())
    cfg["api"]["protect_admin"] = True
    app = create_app(engine=engine, trust_model=trust_model, cfg=cfg)
    w = World(engine, app)
    w.get("/analyst/queue", None, 401)
    w.post("/sim/advance-clock", {"hours": 1}, None, 401)
    w.register("buyer", BUYER, "Karim Buyer")
    w.get("/analyst/queue", "buyer", 403)
    w.make_admin()
    w.get("/analyst/queue", "admin", 200)
    w.post("/sim/advance-clock", {"hours": 1}, "admin", 200)
    clock.reset()
