"""A plain-language intake which creates real business configuration, not demo defaults."""

import sys
from pathlib import Path

from merchmind.journey_models import OnboardingAnswers
from merchmind.models import Merchant, ResearchPolicy, ScoringConfig, decimal_string
from merchmind.storage import private_path, write


def prompt_answers() -> OnboardingAnswers:
    def ask(question: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        print(question + suffix + ": ", end="", file=sys.stderr, flush=True)
        answer = input().strip()
        return answer or default

    def items(question: str, default: str = "") -> list[str]:
        return [part.strip() for part in ask(question, default).split(",") if part.strip()]

    print(
        "Describe your store. Leave optional amounts blank if unknown. Lists use commas.",
        file=sys.stderr,
    )
    return OnboardingAnswers(
        business_name=ask("Business name"),
        merchant_id=ask("Short store ID (letters, numbers and hyphens)", "my-store"),
        market_country=ask("Country code, for example BD", "BD").upper(),
        base_currency=ask("Currency code, for example BDT", "BDT").upper(),
        source_countries=[s.upper() for s in items("Source country codes", "CN")],
        niche=ask("What kind of products do you want to sell?"),
        description=ask("Describe the idea and what you want to avoid"),
        audience_context=items("Who might use these products? (optional)"),
        product_constraints=items("Product restrictions, for example no heavy machines (optional)"),
        excluded_categories=items("Excluded category codes (optional)"),
        sourcing_hosts=items("Approved sourcing hostnames, for example alibaba.com (optional)"),
        research_languages=items("Research languages", "English"),
        max_product_mass_g=ask("Maximum product weight in grams", "400"),
        target_contribution_margin=str(
            decimal_string(ask("Target contribution margin as a percentage", "30").rstrip("%"))
            / 100
        ),
        freight_rate_per_gram=ask("Shipping cost per gram in your currency (optional)") or None,
        startup_budget_local=ask("Total startup budget in your currency (optional)") or None,
    )


def onboard(answers: OnboardingAnswers, workspace: Path) -> tuple[list[Path], list[str]]:
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError(
            "Workspace must be empty; existing merchant inputs will not be overwritten"
        )
    merchant = Merchant(
        merchant_id=answers.merchant_id,
        name=answers.business_name,
        market_country=answers.market_country,
        base_currency=answers.base_currency,
        source_countries=answers.source_countries,
        allowed_marketplaces=answers.sourcing_hosts,
        excluded_categories=answers.excluded_categories,
        constraints={
            "max_product_mass_g": answers.max_product_mass_g,
            "minimum_contribution_margin": answers.target_contribution_margin,
        },
        freight={"rate": answers.freight_rate_per_gram, "currency": answers.base_currency},
        finance={"merchant_vat_treatment": answers.merchant_vat_treatment},
    )
    brief = answers.brief()  # Validate all inputs before writing anything.
    missing = [
        "Research the niche and review the proposed customer groups.",
        "Confirm VAT treatment, dated exchange rates and import tax inputs.",
    ]
    if answers.freight_rate_per_gram is None:
        missing.append("Shipping cost is unknown; cost totals remain blocked until supplied.")
    if not answers.sourcing_hosts:
        missing.append("Choose approved sourcing hosts before collecting supplier listings.")
    workspace.mkdir(parents=True, exist_ok=True)
    return [
        write(private_path(workspace, "merchant.yaml"), merchant),
        write(private_path(workspace, "niche-brief.json"), brief),
        write(private_path(workspace, "scoring.yaml"), ScoringConfig()),
        write(private_path(workspace, "sources.yaml"), ResearchPolicy()),
        write(private_path(workspace, "onboarding.json"), answers),
        write(
            private_path(workspace, "readiness.json"),
            {"status": "needs_research", "missing": missing},
        ),
        write(private_path(workspace, ".gitignore"), "*", text=True),
    ], missing
