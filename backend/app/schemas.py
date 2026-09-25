from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Role(StrEnum):
    TRADE_ANALYST = "TRADE_ANALYST"
    COMPLIANCE_REVIEWER = "COMPLIANCE_REVIEWER"
    SENIOR_CHECKER = "SENIOR_CHECKER"
    COMPLIANCE_MANAGER = "COMPLIANCE_MANAGER"
    INTERNAL_AUDITOR = "INTERNAL_AUDITOR"
    EXECUTIVE_VIEWER = "EXECUTIVE_VIEWER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


DocType = Literal[
    "COMMERCIAL_INVOICE",
    "BILL_OF_LADING",
    "PACKING_LIST",
    "CERTIFICATE_OF_ORIGIN",
    "INSURANCE_CERTIFICATE",
    "INSPECTION_CERTIFICATE",
    "BENEFICIARY_CERTIFICATE",
    "DRAFT",
    "OTHER",
]
Money = Decimal


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=128)


class Terms(StrictModel):
    applicant: str = Field(min_length=3, max_length=150)
    beneficiary: str = Field(min_length=3, max_length=150)
    applicant_country: str = Field(default="Pakistan", max_length=80)
    beneficiary_country: str = Field(default="Singapore", max_length=80)
    issuing_bank: str = Field(default="Meridian Demo Bank", max_length=150)
    advising_bank: str = Field(default="Straits Synthetic Bank", max_length=150)
    confirming_bank: str = Field(default="", max_length=150)
    lc_type: Literal["IMPORT", "EXPORT", "STANDBY"] = "IMPORT"
    currency: Literal["USD", "EUR", "GBP", "PKR", "AED", "CNY", "JPY"] = "USD"
    amount: Decimal = Field(gt=0, le=Decimal("999999999999"), decimal_places=2)
    tolerance_pct: Decimal = Field(default=Decimal("5"), ge=0, le=20, decimal_places=2)
    tolerance_amount: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("999999999"), decimal_places=2)
    issue_date: date
    expiry_date: date
    latest_shipment: date
    presentation_date: date
    presentation_period: int = Field(default=21, ge=1, le=180)
    loading_port: str = Field(min_length=2, max_length=100)
    discharge_port: str = Field(min_length=2, max_length=100)
    place_of_expiry: str = Field(default="Karachi", max_length=100)
    incoterm: Literal["FOB", "CIF", "CFR", "EXW", "FCA", "CPT", "CIP", "DAP", "DDP"] = "CIF"
    goods: str = Field(min_length=3, max_length=1000)
    quantity: Decimal = Field(gt=0, le=Decimal("999999999"), decimal_places=3)
    quantity_unit: str = Field(default="MT", min_length=1, max_length=20)
    unit_price: Decimal = Field(gt=0, le=Decimal("999999999"), decimal_places=4)
    payment_terms: str = Field(default="At sight", max_length=200)
    partial_shipment: bool = False
    transshipment: bool = False
    required_documents: list[DocType] = Field(
        default_factory=lambda: [
            "COMMERCIAL_INVOICE",
            "BILL_OF_LADING",
            "PACKING_LIST",
            "CERTIFICATE_OF_ORIGIN",
        ],
        min_length=1,
        max_length=9,
    )
    special_conditions: str = Field(default="Synthetic demonstration only", max_length=2000)
    rule_profile: Literal["STANDARD_IMPORT_LC", "EXPORT_LC", "HIGH_VALUE_LC", "INSURANCE_REQUIRED"] = (
        "STANDARD_IMPORT_LC"
    )

    @model_validator(mode="after")
    def chronology(self):
        if (
            self.expiry_date < self.issue_date
            or not self.issue_date <= self.latest_shipment <= self.expiry_date
        ):
            raise ValueError("Issue, shipment and expiry dates must be chronologically valid")
        if len(set(self.required_documents)) != len(self.required_documents):
            raise ValueError("Required documents must be unique")
        return self


class CreateLC(StrictModel):
    title: str = Field(min_length=3, max_length=150)
    priority: Literal["STANDARD", "HIGH", "CRITICAL"] = "STANDARD"
    terms: Terms


class EditLC(CreateLC):
    version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)


class DocumentFields(StrictModel):
    number: str = Field(min_length=1, max_length=100)
    issue_date: date
    amount: Decimal | None = Field(default=None, gt=0, le=Decimal("999999999999"), decimal_places=2)
    currency: Literal["USD", "EUR", "GBP", "PKR", "AED", "CNY", "JPY"] | None = None
    quantity: Decimal | None = Field(default=None, gt=0, le=Decimal("999999999"), decimal_places=3)
    unit_price: Decimal | None = Field(default=None, gt=0, le=Decimal("999999999"), decimal_places=4)
    quantity_unit: str | None = Field(default=None, max_length=20)
    applicant: str | None = Field(default=None, max_length=150)
    beneficiary: str | None = Field(default=None, max_length=150)
    consignee: str | None = Field(default=None, max_length=150)
    notify_party: str | None = Field(default=None, max_length=150)
    shipment_date: date | None = None
    loading_port: str | None = Field(default=None, max_length=100)
    discharge_port: str | None = Field(default=None, max_length=100)
    incoterm: str | None = Field(default=None, max_length=10)
    country: str | None = Field(default=None, max_length=80)
    vessel: str | None = Field(default=None, max_length=100)
    partial_shipment: bool = False
    transshipment: bool = False
    line_totals: list[Decimal] = Field(default_factory=list, max_length=200)

    @field_validator("line_totals")
    @classmethod
    def valid_lines(cls, values):
        if any(not v.is_finite() or v <= 0 or v > Decimal("999999999999") for v in values):
            raise ValueError("Line totals must be finite positive amounts")
        return values


class Action(StrictModel):
    action: str = Field(max_length=40)
    version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=2000)
    checklist: list[str] = Field(default_factory=list, max_length=20)


class Note(StrictModel):
    body: str = Field(min_length=3, max_length=4000)


class Assign(StrictModel):
    user_id: str = Field(max_length=36)
    version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)


class Resolve(StrictModel):
    status: Literal["ACKNOWLEDGED", "UNDER_REVIEW", "WAIVED", "REJECTED", "ESCALATED"]
    reason: str = Field(min_length=10, max_length=2000)
    version: int = Field(ge=1)


class ConfigureRule(StrictModel):
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    enabled: bool
    version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=1000)


class UserUpdate(StrictModel):
    role: Role
    active: bool
    reason: str = Field(min_length=10, max_length=1000)


class Simulation(StrictModel):
    invoice_amount: Decimal = Field(gt=0, le=Decimal("999999999999"), decimal_places=2)


class UserCreate(StrictModel):
    name: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=5, max_length=150, pattern=r"^[a-zA-Z0-9._+-]+@lcverify\.demo$")
    role: Role
    password: str = Field(min_length=12, max_length=128)
    reason: str = Field(min_length=10, max_length=1000)


class ResetPassword(StrictModel):
    password: str = Field(min_length=12, max_length=128)
    reason: str = Field(min_length=10, max_length=1000)
