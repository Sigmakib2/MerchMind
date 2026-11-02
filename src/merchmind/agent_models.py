"""Provider-independent contracts for research performed by an external agent."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from merchmind import __version__
from merchmind.models import (
    Evidence,
    Identifier,
    Merchant,
    Model,
    NicheBrief,
    ResearchPolicy,
    SegmentHypothesis,
    SourceLink,
    StarterResearch,
    Versioned,
)
from merchmind.storage import record_hash


class AgentResearchTask(Versioned):
    task_id: Identifier
    created_at: datetime
    expires_at: datetime
    brief: NicheBrief
    merchant_snapshot: Merchant
    policy_snapshot: ResearchPolicy
    research_plan: dict
    source_scope: Literal["approved_hosts", "public_web"] = "approved_hosts"
    allowed_hosts: list[str] = Field(default_factory=list, max_length=50)
    required_capabilities: list[str] = Field(
        default_factory=lambda: [
            "public web browsing or authorized source access",
            "local command execution",
        ]
    )
    instructions: list[str]
    integrity_hash: str = ""

    @field_validator("created_at", "expires_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return Evidence.aware(value)

    @field_validator("allowed_hosts")
    @classmethod
    def hosts(cls, value: list[str]) -> list[str]:
        return Merchant.domains(value)

    @model_validator(mode="after")
    def integrity(self):
        if self.expires_at <= self.created_at:
            raise ValueError("Agent task expiry must follow creation")
        if (
            self.brief.merchant_id != self.merchant_snapshot.merchant_id
            or self.brief.market_country != self.merchant_snapshot.market_country
        ):
            raise ValueError("Agent task merchant/market does not match brief")
        expected = record_hash(self.model_dump(mode="json", exclude={"integrity_hash"}))
        if self.integrity_hash and self.integrity_hash != expected:
            raise ValueError(
                "Agent task integrity hash does not match; prepare a new task instead of editing it"
            )
        self.integrity_hash = expected
        return self


class AgentCapture(Model):
    capture_id: Identifier
    source_uri: SourceLink
    retrieved_at: datetime
    title: str = Field(min_length=1, max_length=300)
    excerpt: str = Field(min_length=10, max_length=10000)

    @field_validator("retrieved_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return Evidence.aware(value)


class AgentActivity(Model):
    action: Literal["search", "browse", "synthesize"]
    performed_at: datetime
    source_uri: SourceLink = None
    query: str | None = Field(default=None, max_length=1500)

    @field_validator("performed_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return Evidence.aware(value)

    @model_validator(mode="after")
    def details(self):
        if self.action == "browse" and self.source_uri is None:
            raise ValueError("Browse activity requires a source URL")
        if self.action == "search" and not self.query:
            raise ValueError("Search activity requires a query")
        return self


class AgentSubmission(Versioned):
    task_id: Identifier
    brief_id: Identifier
    status: Literal["complete", "partial", "unavailable"]
    runtime: str = Field(min_length=1, max_length=200)
    tools_used: list[str] = Field(default_factory=list, max_length=20)
    captures: list[AgentCapture] = Field(default_factory=list, max_length=100)
    activities: list[AgentActivity] = Field(default_factory=list, max_length=500)
    segments: list[SegmentHypothesis] = Field(default_factory=list, max_length=4)
    unresolved: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def references(self):
        ids = [c.capture_id for c in self.captures]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate agent capture IDs")
        uris = [c.source_uri for c in self.captures]
        if len(uris) != len(set(uris)):
            raise ValueError("Combine excerpts from the same source URL into one capture")
        required = {key for s in self.segments for key in [*s.evidence_ids, *s.counterevidence_ids]}
        if required - set(ids):
            raise ValueError("Agent segment references missing captures")
        if self.status == "complete" and (
            not self.captures or len(self.segments) < 3 or not self.tools_used
        ):
            raise ValueError(
                "Complete research needs captures, three/four hypotheses and tool provenance"
            )
        if self.status != "complete" and not self.unresolved:
            raise ValueError("Incomplete research must explain what remains unavailable")
        if self.status == "unavailable" and (self.captures or self.segments):
            raise ValueError(
                "Unavailable research cannot include purported research results; use partial instead"
            )
        return self


class AgentResearchReceipt(Versioned):
    engine_version: str = __version__
    task_id: Identifier
    completed_at: datetime
    status: Literal["complete", "partial", "unavailable"]
    task_snapshot: AgentResearchTask
    submission_snapshot: AgentSubmission
    sources: list[Evidence]
    research: StarterResearch | None
    locally_performed_network_requests: Literal[0] = 0
    warnings: list[str]
