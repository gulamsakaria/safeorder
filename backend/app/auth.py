"""Sandbox accounts: phone number + PIN sign-in.

The PIN is stored only as a salted scrypt hash; the sign-in token is a random string of which only
the SHA-256 is stored. Five wrong PINs lock the account for a while. This protects a demo, it is
not banking-grade security, and the website tells people never to use a real PIN.
"""

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, Request
from sqlmodel import Session, select

from app.api.deps import get_config, get_session
from app.api.errors import ApiError
from app.clock import real_utc_now
from app.enums import UserRole
from app.models import AuthSession, User

PHONE_PATTERN = re.compile(r"^01[3-9]\d{8}$")
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def normalize_phone(raw: str) -> str:
    """Bangladeshi mobile number as 11 digits (01XXXXXXXXX). +880 and spaces are accepted."""
    digits = re.sub(r"[\s\-]", "", raw)
    if digits.startswith("+880"):
        digits = "0" + digits[4:]
    elif digits.startswith("880") and len(digits) == 13:
        digits = "0" + digits[3:]
    if not PHONE_PATTERN.match(digits):
        raise ApiError(422, "VALIDATION_ERROR", "phone must look like 01XXXXXXXXX")
    return digits


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def validate_pin(pin: str, cfg: dict[str, Any]) -> None:
    digits = cfg["wallet"]["pin_digits"]
    if not re.fullmatch(rf"\d{{{digits}}}", pin):
        raise ApiError(422, "VALIDATION_ERROR", f"the PIN must be exactly {digits} digits")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_pin(session: Session, user: User, pin: str, cfg: dict[str, Any]) -> None:
    """Verify a PIN with lockout. Raises ApiError; commits the failure counter itself."""
    now = real_utc_now()
    if user.locked_until is not None and _aware(user.locked_until) > now:
        raise ApiError(429, "ACCOUNT_LOCKED", "too many wrong PINs, try again later")
    if verify_pin(pin, user.pin_hash):
        if user.failed_pins:
            user.failed_pins = 0
            session.add(user)
            session.commit()
        return
    user.failed_pins += 1
    if user.failed_pins >= cfg["wallet"]["max_pin_attempts"]:
        user.failed_pins = 0
        user.locked_until = now + timedelta(minutes=cfg["wallet"]["lock_minutes"])
    session.add(user)
    session.commit()
    raise ApiError(401, "WRONG_PIN", "the phone number or PIN is wrong")


def _aware(value: datetime) -> datetime:
    from datetime import UTC

    return value if value.tzinfo else value.replace(tzinfo=UTC)


def start_session(session: Session, user: User, cfg: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(32)
    now = real_utc_now()
    session.add(
        AuthSession(
            token_hash=_token_hash(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=cfg["wallet"]["session_days"]),
        )
    )
    session.commit()
    return token


def end_session(session: Session, token: str) -> None:
    row = session.get(AuthSession, _token_hash(token))
    if row is not None:
        session.delete(row)
        session.commit()


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def user_from_token(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = session.get(AuthSession, _token_hash(token))
    if row is None or _aware(row.expires_at) <= real_utc_now():
        return None
    return session.get(User, row.user_id)


def optional_user(request: Request, session: Session = Depends(get_session)) -> User | None:
    return user_from_token(session, bearer_token(request))


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise ApiError(401, "NOT_SIGNED_IN", "please sign in")
    if user.frozen:
        raise ApiError(403, "ACCOUNT_FROZEN", "this account is frozen by an admin")
    return user


def current_admin(user: User = Depends(current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise ApiError(403, "ADMIN_ONLY", "admins only")
    return user


def current_seller(user: User = Depends(current_user)) -> User:
    if user.seller_id is None:
        raise ApiError(403, "NOT_A_SELLER", "turn on seller mode first")
    return user


def protect_admin_enabled(cfg: dict[str, Any] = Depends(get_config)) -> bool:
    return bool(cfg["api"].get("protect_admin", False))


def ensure_admin_account(session: Session, phone: str, pin: str, cfg: dict[str, Any]) -> User:
    """Create or update the admin from the environment (SAFEORDER_ADMIN_PHONE and _PIN)."""
    from app.accounts import create_user

    phone = normalize_phone(phone)
    validate_pin(pin, cfg)
    user = session.exec(select(User).where(User.phone == phone)).first()
    if user is None:
        user = create_user(session, phone=phone, name="Admin", pin=pin, cfg=cfg, bonus=False)
    user.role = UserRole.ADMIN
    user.pin_hash = hash_pin(pin)
    session.add(user)
    session.commit()
    return user
