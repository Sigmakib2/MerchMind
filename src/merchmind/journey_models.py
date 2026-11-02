"""Contracts for onboarding, connected research, validation and launch planning."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from merchmind import __version__
from merchmind.models import (
    CostInput,
    Currency,
    Dec,
    Economics,
    Evidence,
    Identifier,
    Merchant,
    Model,
    NicheBrief,
    Nonnegative,
    Positive,
    Ratio,
    StarterProfile,
    StarterResearch,
    SupplierQuote,
    Versioned,
    decimal_string,
)


class OnboardingAnswers(Versioned):
    merchant_id: Identifier
    business_name: str = Field(min_length=1, max_length=200)
    market_country: str
    base_currency: Currency
    source_countries: list[str] = Field(default_factory=lambda: ["CN"], min_length=1)
    niche: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=2000)
    audience_context: list[str] = Field(default_factory=list)
    product_constraints: list[str] = Field(default_factory=list)
    excluded_categories: list[str] = Field(default_factory=list)
    sourcing_hosts: list[str] = Field(default_factory=list)
    research_languages: list[str] = Field(default_factory=lambda: ["English"])
    max_product_mass_g: Positive
    target_contribution_margin: Ratio = "0.30"
    freight_rate_per_gram: Nonnegative | None = None
    startup_budget_local: Positive | None = None
    merchant_vat_treatment: Literal["recoverable", "expense", "unknown"] = "unknown"

    @field_validator("market_country")
    @classmethod
    def valid_country(cls, value: str) -> str:
        return Merchant.country(value)

    @field_validator("source_countries")
    @classmethod
    def valid_sources(cls, value: list[str]) -> list[str]:
        return Merchant.countries(value)

    @field_validator("sourcing_hosts")
    @classmethod
    def valid_hosts(cls, value: list[str]) -> list[str]:
        return Merchant.domains(value)

    def brief(self) -> NicheBrief:
        return NicheBrief(
            brief_id=f"niche-{self.merchant_id[:70]}",
            merchant_id=self.merchant_id,
            niche=self.niche,
            description=self.description,
            market_country=self.market_country,
            audience_context=self.audience_context,
            product_constraints=self.product_constraints,
            sourcing_hosts=self.sourcing_hosts,
            research_languages=self.research_languages,
        )


class ResearchConnection(Versioned):
    search_provider: Literal["brave"] = "brave"
    synthesis_provider: Literal["deepseek"] = "deepseek"
    model: str = Field(min_length=1, max_length=100)
    search_key_env: str = Field(default="BRAVE_SEARCH_API_KEY", pattern=r"^[A-Z][A-Z0-9_]{0,79}$")
    model_key_env: str = Field(default="DEEPSEEK_API_KEY", pattern=r"^[A-Z][A-Z0-9_]{0,79}$")
    research_hosts: list[str] = Field(min_length=1, max_length=10)
    max_search_queries: int = Field(default=4, ge=1, le=8)
    results_per_query: int = Field(default=5, ge=1, le=10)
    max_input_characters: int = Field(default=20000, ge=2000, le=50000)
    max_output_tokens: int = Field(default=4096, ge=512, le=8192)
    search_price_per_request_usd: Nonnegative | None = None
    model_input_price_per_million_usd: Nonnegative | None = None
    model_output_price_per_million_usd: Nonnegative | None = None
    max_estimated_cost_usd: Positive

    @field_validator("research_hosts")
    @classmethod
    def valid_hosts(cls, value: list[str]) -> list[str]:
        return Merchant.domains(value)


class ConnectedResearchResult(Versioned):
    engine_version: str = __version__
    run_id: Identifier
    brief_id: Identifier
    run_at: datetime
    status: Literal["complete", "partial"]
    research: StarterResearch | None
    sources: list[Evidence]
    requests: list[dict]
    configured_cost_upper_estimate_usd: Nonnegative
    warnings: list[str]
    connection_snapshot: ResearchConnection
    brief_snapshot: NicheBrief
    model_usage: dict[str, int] = Field(default_factory=dict)


HypothesisField = Literal[
    "use_context", "possible_goals", "possible_buying_triggers", "possible_objections"
]


class ProductFact(Model):
    attribute: Identifier
    value: str = Field(min_length=1, max_length=500)
    evidence_ids: list[Identifier] = Field(min_length=1)


class CandidateProduct(Model):
    product_id: Identifier
    name: str = Field(min_length=1, max_length=200)
    variant: str = Field(min_length=1, max_length=200)
    category: str
    mass_g: Positive | None
    facts: list[ProductFact] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def unique_attributes(self):
        names = [f.attribute for f in self.facts]
        if len(names) != len(set(names)):
            raise ValueError(
                "Product facts must have unique attributes; resolve contradictory values explicitly"
            )
        return self


class FitCriterion(Model):
    criterion_id: Identifier
    segment_id: Identifier
    hypothesis_field: HypothesisField
    hypothesis_index: int = Field(default=0, ge=0, le=9)
    description: str = Field(min_length=3, max_length=1000)
    product_attribute: Identifier
    operator: Literal["equals", "contains", "lte", "gte"]
    expected_value: str = Field(min_length=1, max_length=500)
    weight: Positive = "1"

    @model_validator(mode="after")
    def numeric_operators(self):
        if self.operator in {"lte", "gte"}:
            decimal_string(self.expected_value)
        return self


class ComparisonInput(Versioned):
    profile_id: Identifier
    profile_version: str
    products: list[CandidateProduct] = Field(min_length=1, max_length=20)
    criteria: list[FitCriterion] = Field(min_length=1, max_length=80)
    sources: list[Evidence] = Field(default_factory=list, max_length=100)
    minimum_coverage: Ratio = "0.60"

    @model_validator(mode="after")
    def references(self):
        for items, key in (
            (self.products, "product_id"),
            (self.criteria, "criterion_id"),
            (self.sources, "evidence_id"),
        ):
            ids = [getattr(v, key) for v in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {key}")
        source_ids = {e.evidence_id for e in self.sources}
        required = {key for p in self.products for fact in p.facts for key in fact.evidence_ids}
        required.update(key for e in self.sources for key in e.supporting_evidence_ids)
        if required - source_ids:
            raise ValueError("Product comparison references missing evidence")
        return self


class CriterionMatch(Model):
    criterion_id: Identifier
    description: str
    original_hypothesis: str
    status: Literal["match", "mismatch", "unknown"]
    expected_value: str
    observed_value: str | None
    evidence_ids: list[Identifier]
    reason: str


class SegmentMatch(Model):
    product_id: Identifier
    product_name: str
    segment_id: Identifier
    segment_name: str
    coverage: Ratio
    attribute_match_score: Dec | None
    verdict: Literal["possible_fit", "poor_fit", "insufficient_evidence", "excluded"]
    checks: list[CriterionMatch]
    constraints: list[str]


class ComparisonReport(Versioned):
    engine_version: str = __version__
    compared_at: datetime
    profile_id: Identifier
    profile_version: str
    results: list[SegmentMatch]
    input_snapshot: ComparisonInput
    profile_snapshot: StarterProfile
    sources: list[Evidence]
    limitations: list[str]


class ValidationEvent(Versioned):
    event_id: Identifier
    study_id: Identifier
    profile_id: Identifier
    profile_version: str
    segment_id: Identifier
    hypothesis_field: HypothesisField
    hypothesis_index: int = Field(default=0, ge=0, le=9)
    method: Literal["interview", "survey", "sample_test", "sales", "returns"]
    outcome: Literal["supports", "contradicts", "inconclusive"]
    occurred_at: datetime
    recorded_at: datetime
    reviewed_by_merchant: Literal[True]
    sample_size: int = Field(gt=0, strict=True)
    notes: str = Field(min_length=3, max_length=2000)
    evidence_ids: list[Identifier] = Field(min_length=1)
    sources: list[Evidence] = Field(min_length=1, max_length=30)
    supersedes_event_id: Identifier | None = None

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return Evidence.aware(value)

    @model_validator(mode="after")
    def references_and_time(self):
        ids = [s.evidence_id for s in self.sources]
        required = set(self.evidence_ids)
        required.update(key for source in self.sources for key in source.supporting_evidence_ids)
        if len(ids) != len(set(ids)) or required - set(ids):
            raise ValueError("Validation evidence is duplicated or missing")
        if self.occurred_at > self.recorded_at:
            raise ValueError("An observation cannot occur after it is recorded")
        if self.supersedes_event_id == self.event_id:
            raise ValueError("A validation event cannot supersede itself")
        return self


class ValidationRecord(Versioned):
    event: ValidationEvent
    event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    saved_at: datetime


class ValidationFinding(Model):
    segment_id: Identifier
    hypothesis_field: HypothesisField
    hypothesis_index: int
    hypothesis: str
    assessment: Literal["untested", "some_support", "contradicted", "mixed", "inconclusive"]
    supporting_studies: int
    contradicting_studies: int
    inconclusive_studies: int
    reported_sample_total: int
    event_ids: list[Identifier]
    methods: list[str]


class ValidationSummary(Versioned):
    engine_version: str = __version__
    profile_id: Identifier
    profile_version: str
    summarized_at: datetime
    findings: list[ValidationFinding]
    records: list[ValidationRecord]
    limitations: list[str]


class LaunchInput(Versioned):
    currency: Currency
    cost_input: CostInput
    supplier_quote: SupplierQuote
    order_quantity: int = Field(gt=0, le=1000000, strict=True)
    sample_cost_local: Nonnegative | None
    setup_cost_local: Nonnegative | None
    initial_ad_budget_local: Nonnegative | None
    upfront_selling_costs_local: Nonnegative | None
    working_capital_reserve_local: Nonnegative | None
    contingency_ratio: Ratio | None
    available_budget_local: Nonnegative | None
    cash_evidence_ids: list[Identifier] = Field(min_length=1)
    sources: list[Evidence] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def references(self):
        ids = [s.evidence_id for s in self.sources]
        required = set(
            self.cash_evidence_ids
            + self.cost_input.evidence_ids
            + self.supplier_quote.evidence_ids
            + [self.cost_input.fx.evidence_id]
        )
        required.update(key for s in self.cost_input.scenarios for key in s.tax_evidence_ids)
        required.update(key for s in self.sources for key in s.supporting_evidence_ids)
        if len(ids) != len(set(ids)) or required - set(ids):
            raise ValueError("Launch budget evidence is duplicated or missing")
        return self


class LaunchScenario(Model):
    name: Literal["optimistic", "base", "conservative"]
    status: Literal["estimated", "not_estimated"]
    cash_items: dict[str, Nonnegative | None]
    required_cash: Nonnegative | None
    budget_status: Literal["within_budget", "over_budget", "budget_unknown", "not_estimated"]
    budget_remaining: Dec | None
    missing: list[str]


class LaunchReport(Versioned):
    engine_version: str = __version__
    estimated_at: datetime
    merchant_id: Identifier
    currency: Currency
    order_quantity: int
    scenarios: list[LaunchScenario]
    economics: Economics
    input_snapshot: LaunchInput
    merchant_snapshot: Merchant
    sources: list[Evidence]
    assumptions: list[str]
