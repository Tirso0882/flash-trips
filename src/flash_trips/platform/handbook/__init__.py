"""Format-neutral Handbook compilation and deterministic HTML rendering."""

from dataclasses import dataclass
from datetime import datetime
from html import escape

# SKELETON_REPLACEMENT: issue 220 (FT-22) deepens this thin Handbook station.


@dataclass(frozen=True, slots=True)
class HandbookClaim:
    text: str
    evidence_reference: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class HandbookDocument:
    """Schema-versioned semantic content independent of an export format."""

    schema_version: int
    plan_revision_id: str
    revision_number: int
    claims: tuple[HandbookClaim, ...]


def compile_document(
    *,
    plan_revision_id: str,
    revision_number: int,
    claims: tuple[HandbookClaim, ...],
) -> HandbookDocument:
    if not plan_revision_id or revision_number < 1 or not claims:
        raise ValueError("A Handbook Document requires a complete Plan Revision")
    return HandbookDocument(
        schema_version=1,
        plan_revision_id=plan_revision_id,
        revision_number=revision_number,
        claims=claims,
    )


def render_html(document: HandbookDocument) -> bytes:
    """Render a stable, script-free UTF-8 projection of a Handbook Document."""

    claims = "".join(
        "<li>"
        f"<p>{escape(claim.text)}</p>"
        f"<p>Evidence: {escape(claim.evidence_reference)}, observed "
        f'<time datetime="{escape(claim.observed_at.isoformat())}">'
        f"{escape(claim.observed_at.isoformat())}</time></p>"
        "</li>"
        for claim in document.claims
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>Trip Handbook, Plan Revision {document.revision_number}</title>"
        "</head><body><main>"
        f"<h1>Trip Handbook</h1><p>Plan Revision {document.revision_number}: "
        f"<code>{escape(document.plan_revision_id)}</code></p>"
        f"<ul>{claims}</ul>"
        "</main></body></html>"
    ).encode()


__all__ = [
    "HandbookClaim",
    "HandbookDocument",
    "compile_document",
    "render_html",
]
