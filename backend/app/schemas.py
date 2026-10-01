"""Pydantic API schemas. Hidden ground-truth fields are deliberately absent here.

``Seller.archetype`` and ``Seller.is_high_risk`` exist only in the database model.
A test asserts that no schema in this module exposes them.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

HIDDEN_FIELDS = frozenset({"archetype", "is_high_risk"})


class SellerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    wallet_no: str
    created_at: datetime
    category: str


class BuyerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    wallet_no: str
    created_at: datetime
