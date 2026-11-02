"""Versioned, runtime-validated contracts. Commercial decimals travel as strings."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator


def decimal_string(value: object) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Commercial decimals must be quoted strings, not JSON numbers")
    if isinstance(value, str) and len(value) > 1024:
        raise ValueError("Decimal exceeds supported precision or exponent range")
    try:
        result = Decimal(value)
    except Exception as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("Decimal must be finite")
    if (
        len(result.as_tuple().digits) > 1000
        or abs(result.as_tuple().exponent) > 1000
        or abs(result.adjusted()) > 1000
    ):
        raise ValueError("Decimal exceeds supported precision or exponent range")
    return result


Dec = Annotated[Decimal, BeforeValidator(decimal_string, json_schema_input_type=str)]
Nonnegative = Annotated[Dec, Field(ge=0)]
Positive = Annotated[Dec, Field(gt=0)]
Ratio = Annotated[Dec, Field(ge=0, le=1)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")]
COUNTRIES = set(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split()
)
CURRENCIES = set(
    "AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VED VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWG".split()
)


def currency_code(value: str) -> str:
    if value not in CURRENCIES:
        raise ValueError("Unsupported ISO 4217 currency code")
    return value


Currency = Annotated[
    str, BeforeValidator(currency_code), Field(json_schema_extra={"enum": sorted(CURRENCIES)})
]


def source_link(value: str | None) -> str | None:
    if value is None:
        return None
    if any(ord(c) <= 32 or ord(c) == 127 or c in "<>\\`" for c in value):
        raise ValueError("Source link contains unsafe characters")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Source links must use HTTPS without embedded credentials")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


SourceLink = Annotated[str | None, BeforeValidator(source_link)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class Versioned(Model):
    schema_version: Literal["1.0"] = "1.0"


class Freight(Model):
    mode: Literal["per_gram", "fixed_per_unit"] = "per_gram"
    rate: Nonnegative | None
    currency: Currency
    rate_basis: Literal["billable_mass"] = "billable_mass"
    minimum_charge: Nonnegative = Decimal("0")
    customs_included: Literal[False] = False


class Constraints(Model):
    max_product_mass_g: Positive = Decimal("400")
    minimum_contribution_margin: Ratio = Decimal("0.30")
    require_positive_conservative_margin: bool = True


class Finance(Model):
    fx_policy: Literal["dated_source_required"] = "dated_source_required"
    import_tax_policy: Literal["manual_verified_input"] = "manual_verified_input"
    merchant_vat_treatment: Literal["recoverable", "expense", "unknown"] = "unknown"
    max_fx_age_days: int = Field(default=30, ge=0, le=365)


class Permissions(Model):
    read_only_research: Literal[True] = True
    outbound_messages: Literal[False] = False
    purchasing: Literal[False] = False


class ResearchPolicy(Versioned):
    max_requests_per_domain: int = Field(default=3, ge=2, le=50)
    max_response_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    max_sources: int = Field(default=20, ge=1, le=100)
    max_duration_minutes: int = Field(default=30, ge=1, le=60)
    max_report_bytes: int = Field(default=10_000_000, ge=1024, le=100_000_000)


class Merchant(Versioned):
    merchant_id: Identifier
    name: str = Field(min_length=1, max_length=200)
    market_country: str
    base_currency: Currency
    source_countries: list[str] = Field(min_length=1)
    allowed_marketplaces: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    excluded_categories: list[str] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    freight: Freight
    finance: Finance = Field(default_factory=Finance)
    permissions: Permissions = Field(default_factory=Permissions)

    @field_validator("market_country")
    @classmethod
    def country(cls, value: str) -> str:
        if value not in COUNTRIES:
            raise ValueError("Invalid ISO 3166 country code")
        return value

    @field_validator("source_countries")
    @classmethod
    def countries(cls, value: list[str]) -> list[str]:
        for item in value:
            cls.country(item)
        return value

    @field_validator("allowed_marketplaces")
    @classmethod
    def domains(cls, value: list[str]) -> list[str]:
        import re

        if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", d) for d in value):
            raise ValueError("Allowlist entries must be lowercase hostnames, without paths")
        return value

    @model_validator(mode="after")
    def freight_currency(self) -> Self:
        if self.freight.currency != self.base_currency:
            raise ValueError("Freight rate must use the merchant base currency")
        return self


class Evidence(Versioned):
    evidence_id: Identifier
    source_type: Literal[
        "merchant_record",
        "manufacturer",
        "supplier_quote",
        "marketplace_listing",
        "independent_review",
        "government",
        "inference",
        "web_search_result",
        "agent_web_capture",
    ]
    source_uri: SourceLink = None
    source_record_ref: str
    retrieved_at: datetime
    assertion: str
    captured_value: str | None = None
    currency: Currency | None = None
    unit: str | None = None
    verification_status: Literal["merchant_provided", "unverified", "verified", "inferred"]
    freshness_status: Literal["current", "stale", "unknown"] = "unknown"
    hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    supporting_evidence_ids: list[Identifier] = Field(default_factory=list)

    @field_validator("retrieved_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timestamps require a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def inference(self) -> Self:
        if self.source_type == "inference" and (
            self.verification_status != "inferred" or not self.supporting_evidence_ids
        ):
            raise ValueError("Inferences must be labeled and cite supporting evidence")
        return self


class Product(Model):
    product_id: Identifier
    name: str = Field(min_length=1)
    category: str
    variant: str = Field(min_length=1)
    mass_g: Positive | None = None


class OrderLine(Model):
    order_id_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    product_id: Identifier
    date: date
    quantity: int = Field(gt=0, strict=True)
    unit_price: Nonnegative
    currency: Currency
    order_status: Literal["pending", "cancelled", "fulfilled"]
    fulfilled_count: int = Field(ge=0, strict=True)
    returned_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def counts(self) -> Self:
        if not 0 <= self.returned_count <= self.fulfilled_count <= self.quantity:
            raise ValueError("Require returned <= fulfilled <= quantity")
        if self.order_status != "fulfilled" and self.fulfilled_count:
            raise ValueError("Unfulfilled orders cannot have fulfilled units")
        return self


class Return(Model):
    return_id: Identifier
    product_id: Identifier
    quantity: int = Field(gt=0, strict=True)
    reason_code: str
    date: date
    associated_cost: Nonnegative | None = None


class PriceTier(Model):
    min_qty: int = Field(gt=0, strict=True)
    unit_price: Positive
    currency: Currency


class SupplierQuote(Versioned):
    supplier_id: Identifier
    source: str
    listing_url: SourceLink = None
    product_variant_key: str
    price_tiers: list[PriceTier] = Field(min_length=1)
    moq: int = Field(gt=0, strict=True)
    mass_g: Positive | None = None
    packaging_mass_g: Nonnegative | None = None
    incoterm: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    quote_type: Literal["advertised", "confirmed"]
    quoted_at: datetime
    valid_until: datetime | None = None
    evidence_ids: list[Identifier] = Field(min_length=1)
    verification_flags: list[str] = Field(default_factory=list)
    verification_checks: dict[str, bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def tiers(self) -> Self:
        Evidence.aware(self.quoted_at)
        if self.valid_until is not None:
            Evidence.aware(self.valid_until)
            if self.valid_until < self.quoted_at:
                raise ValueError("Quote expiry precedes quote date")
        quantities = [p.min_qty for p in self.price_tiers]
        if quantities != sorted(set(quantities)) or quantities[0] != self.moq:
            raise ValueError("Price tiers must be unique, sorted and start at MOQ")
        if len({p.currency for p in self.price_tiers}) != 1:
            raise ValueError("Quote tiers must use one currency")
        return self


class Comparable(Model):
    retailer: str
    product_match_type: Literal["exact", "similar", "unknown"]
    product_variant_key: str
    price: Positive
    currency: Currency
    market: str
    captured_at: datetime
    source_url: Annotated[str, BeforeValidator(source_link)]
    evidence_id: Identifier
    price_type: Literal["advertised", "transaction"] = "advertised"

    @field_validator("captured_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return Evidence.aware(value)


class FX(Model):
    source_currency: Currency
    target_currency: Currency
    rate: Positive
    as_of: datetime
    evidence_id: Identifier

    @field_validator("as_of")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return Evidence.aware(value)


class Mass(Model):
    value: Positive
    unit: Literal["g", "kg"]

    def grams(self) -> Decimal:
        return self.value * (Decimal("1000") if self.unit == "kg" else Decimal("1"))


class CostScenario(Model):
    name: Literal["optimistic", "base", "conservative"]
    unit_price_source: Positive
    mass_g: Positive | None = None
    packaging_mass_g: Nonnegative | None = None
    mass: Mass | None = None
    packaging_mass: Mass | None = None
    volumetric_mass_g: Nonnegative | None = None
    fixed_sourcing_per_unit: Nonnegative = Decimal("0")
    import_duties: Nonnegative | None
    import_vat: Nonnegative | None
    tax_inputs_confirmed: bool = False
    tax_evidence_ids: list[Identifier] = Field(default_factory=list)
    brokerage: Nonnegative | None
    local_inbound: Nonnegative | None
    other_import_costs: Nonnegative | None
    selling_price_net: Positive
    packaging: Nonnegative | None
    fulfillment: Nonnegative | None
    payment_fee: Nonnegative | None
    marketing_cost: Nonnegative | None
    expected_return_loss: Nonnegative | None

    @model_validator(mode="after")
    def normalize_mass(self) -> Self:
        for source, target in (("mass", "mass_g"), ("packaging_mass", "packaging_mass_g")):
            mass = getattr(self, source)
            if mass is not None:
                grams = mass.grams()
                existing = getattr(self, target)
                if existing is not None and existing != grams:
                    raise ValueError(f"{source} conflicts with {target}")
                setattr(self, target, grams)
        return self


class CostInput(Versioned):
    merchant_id: Identifier
    product_variant_key: str
    origin_country: str
    destination_country: str
    fx: FX
    evidence_ids: list[Identifier] = Field(min_length=1)
    scenarios: list[CostScenario] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def countries_and_scenarios(self) -> Self:
        Merchant.country(self.origin_country)
        Merchant.country(self.destination_country)
        if {s.name for s in self.scenarios} != {"optimistic", "base", "conservative"}:
            raise ValueError("Supply exactly one of each scenario")
        return self


CRITERIA = (
    "customer_fit",
    "contribution_economics",
    "demand_evidence",
    "supplier_reliability",
    "operational_suitability",
    "differentiation",
)


class Weights(Model):
    customer_fit: Ratio = Decimal("0.30")
    contribution_economics: Ratio = Decimal("0.25")
    demand_evidence: Ratio = Decimal("0.15")
    supplier_reliability: Ratio = Decimal("0.15")
    operational_suitability: Ratio = Decimal("0.10")
    differentiation: Ratio = Decimal("0.05")

    @model_validator(mode="after")
    def total(self) -> Self:
        if sum(getattr(self, key) for key in CRITERIA) != Decimal("1"):
            raise ValueError("Scoring weights must sum to exactly 1")
        return self


class ScoringConfig(Versioned):
    weights: Weights = Field(default_factory=Weights)
    minimum_coverage: Ratio = Decimal("0.75")
    test_threshold: Annotated[Dec, Field(ge=0, le=100)] = Decimal("70")
    scoring_version: Literal["1.0"] = "1.0"


class Signal(Model):
    score: Annotated[Dec, Field(ge=0, le=100)]
    evidence_ids: list[Identifier] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ResearchRequest(Versioned):
    request_id: Identifier
    merchant_id: Identifier
    mode: Literal["targeted"] = "targeted"
    product_url: str | None = None
    product_name: str | None = None
    product_variant_key: str | None = None
    category: str | None = None
    safety_review: Literal["pending", "approved", "blocked"] = "pending"
    safety_evidence_ids: list[Identifier] = Field(default_factory=list)
    market_country: str
    max_sources: int = Field(default=20, ge=1, le=100)
    max_duration_minutes: int = Field(default=30, ge=1, le=60)
    max_estimated_api_cost_usd: Nonnegative = Decimal("1")
    require_human_approval_for_external_actions: Literal[True] = True

    @model_validator(mode="after")
    def identity(self) -> Self:
        Merchant.country(self.market_country)
        if not self.product_url and not self.product_name:
            raise ValueError("Provide a product URL or name")
        return self


class Finding(Model):
    finding_id: Identifier
    segment_id: str
    statement: str
    kind: Literal["observation", "merchant_hypothesis", "inference"]
    confidence: Literal["low", "medium", "high"]
    evidence_ids: list[Identifier]
    counterevidence_ids: list[Identifier] = Field(default_factory=list)
    last_reviewed_at: datetime
    adopted: Literal[False] = False


class CustomerProfile(Versioned):
    merchant_id: Identifier
    built_at: datetime
    profile_version: str
    metrics: list[dict]
    findings: list[Finding]
    limitations: list[str]
    evidence_ids: list[Identifier]


class NicheBrief(Versioned):
    brief_id: Identifier
    merchant_id: Identifier
    niche: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=2000)
    market_country: str
    audience_context: list[str] = Field(default_factory=list, max_length=20)
    product_constraints: list[str] = Field(default_factory=list, max_length=20)
    sourcing_hosts: list[str] = Field(default_factory=list, max_length=20)
    research_languages: list[str] = Field(
        default_factory=lambda: ["English"], min_length=1, max_length=5
    )
    segment_count: Literal[3, 4] = 4

    @field_validator("market_country")
    @classmethod
    def country(cls, value: str) -> str:
        return Merchant.country(value)

    @field_validator("sourcing_hosts")
    @classmethod
    def domains(cls, value: list[str]) -> list[str]:
        return Merchant.domains(value)


class SegmentHypothesis(Model):
    segment_id: Identifier
    name: str = Field(min_length=3, max_length=150)
    use_context: str = Field(min_length=10, max_length=1000)
    possible_goals: list[str] = Field(min_length=1, max_length=10)
    possible_buying_triggers: list[str] = Field(min_length=1, max_length=10)
    possible_objections: list[str] = Field(min_length=1, max_length=10)
    product_search_terms: list[str] = Field(min_length=1, max_length=10)
    validation_questions: list[str] = Field(min_length=1, max_length=10)
    kind: Literal["merchant_hypothesis", "research_inference"] = "merchant_hypothesis"
    confidence: Literal["low", "medium"] = "low"
    evidence_ids: list[Identifier] = Field(default_factory=list)
    counterevidence_ids: list[Identifier] = Field(default_factory=list)
    status: Literal["unvalidated"] = "unvalidated"

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if self.kind == "research_inference" and not self.evidence_ids:
            raise ValueError("Research inferences must cite supporting evidence")
        if self.kind == "merchant_hypothesis" and self.confidence != "low":
            raise ValueError("Unresearched merchant hypotheses must have low confidence")
        if set(self.evidence_ids) & set(self.counterevidence_ids):
            raise ValueError("Supporting and contradicting evidence must be distinct")
        return self


class StarterResearch(Versioned):
    brief_id: Identifier
    segments: list[SegmentHypothesis] = Field(min_length=3, max_length=4)
    sources: list[Evidence] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def references(self) -> Self:
        source_ids = [e.evidence_id for e in self.sources]
        segment_ids = [s.segment_id for s in self.segments]
        names = [s.name.casefold().strip() for s in self.segments]
        contexts = [s.use_context.casefold().strip() for s in self.segments]
        if len(source_ids) != len(set(source_ids)) or len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Duplicate source or segment IDs")
        if len(names) != len(set(names)):
            raise ValueError("Segments must have distinct names")
        if len(contexts) != len(set(contexts)):
            raise ValueError("Segments must describe distinct use contexts")
        required = {key for s in self.segments for key in [*s.evidence_ids, *s.counterevidence_ids]}
        required.update(key for e in self.sources for key in e.supporting_evidence_ids)
        if required - set(source_ids):
            raise ValueError(f"Unknown starter evidence IDs: {sorted(required - set(source_ids))}")
        return self


class StarterProfile(Versioned):
    profile_id: Identifier
    profile_version: str
    merchant_id: Identifier
    built_at: datetime
    mode: Literal["starter"] = "starter"
    status: Literal["hypotheses_unvalidated"] = "hypotheses_unvalidated"
    sales_history_used: Literal[False] = False
    brief: NicheBrief
    research: StarterResearch
    missing_evidence: list[str]
    limitations: list[str]

    @model_validator(mode="after")
    def matching_brief(self) -> Self:
        if (
            self.brief.merchant_id != self.merchant_id
            or self.research.brief_id != self.brief.brief_id
        ):
            raise ValueError("Starter profile identity does not match brief")
        if len(self.research.segments) != self.brief.segment_count:
            raise ValueError("Segment count differs from requested count")
        return self


class Feedback(Versioned):
    run_id: Identifier
    status: Literal["approved_for_sample", "rejected", "sample_tested", "actual_order_outcome"]
    recorded_at: datetime
    notes: str


class ScenarioResult(Model):
    name: Literal["optimistic", "base", "conservative"]
    status: Literal["complete", "not_estimated"]
    missing: list[str]
    currency: Currency
    breakdown: dict[str, Dec | None]
    landed: Nonnegative | None
    contribution: Dec | None
    contribution_margin: Dec | None


class Economics(Model):
    status: Literal["complete", "not_estimated"]
    scenarios: list[ScenarioResult]
    assumptions: list[str]
    evidence_ids: list[Identifier]
    input_snapshot: CostInput | None = None


class Evaluation(Model):
    score: Annotated[Dec, Field(ge=0, le=100)] | None
    coverage: Ratio
    decision: Literal["test", "investigate", "reject"]
    scoring_version: str
    components: dict[str, Signal | None]
    blockers: list[str]
    rationale: str
    policy: ScoringConfig


class Identity(Model):
    name: str
    variant: str | None
    match_status: Literal["specified_by_merchant", "needs_review"]


class Report(Versioned):
    run_id: Identifier
    merchant_id: Identifier
    request_id: Identifier
    run_at: datetime
    engine_version: str
    product_identity: Identity
    customer_fit: Signal | None
    supplier_options: list[SupplierQuote]
    local_comparables: list[Comparable]
    economics: Economics
    evaluation: Evaluation
    missing_evidence: list[str]
    sources: list[Evidence]
    source_statuses: list[dict]
    merchant_snapshot: Merchant
    request_snapshot: ResearchRequest
    research_policy: ResearchPolicy = Field(default_factory=ResearchPolicy)

    @model_validator(mode="after")
    def references(self) -> Self:
        ids = [e.evidence_id for e in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evidence IDs")
        required = set(self.economics.evidence_ids)
        required.update(self.request_snapshot.safety_evidence_ids)
        for evidence in self.sources:
            required.update(evidence.supporting_evidence_ids)
        for quote in self.supplier_options:
            required.update(quote.evidence_ids)
        required.update(c.evidence_id for c in self.local_comparables)
        for signal in self.evaluation.components.values():
            if signal:
                required.update(signal.evidence_ids)
        if self.customer_fit:
            required.update(self.customer_fit.evidence_ids)
        if self.economics.input_snapshot:
            cost = self.economics.input_snapshot
            required.add(cost.fx.evidence_id)
            required.update(cost.evidence_ids)
            for scenario in cost.scenarios:
                required.update(scenario.tax_evidence_ids)
        missing = required - set(ids)
        if missing:
            raise ValueError(f"Unknown evidence IDs: {sorted(missing)}")
        if self.request_snapshot.merchant_id != self.merchant_id:
            raise ValueError("Request merchant does not match report")
        if self.merchant_snapshot.merchant_id != self.merchant_id:
            raise ValueError("Merchant snapshot does not match report")
        if self.request_id != self.request_snapshot.request_id:
            raise ValueError("Request ID does not match snapshot")
        if self.product_identity.variant != self.request_snapshot.product_variant_key:
            raise ValueError("Product variant does not match request snapshot")
        if self.customer_fit != self.evaluation.components.get("customer_fit"):
            raise ValueError("Customer fit does not match evaluated component")
        return self
