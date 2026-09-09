from datetime import UTC, datetime

from flash_trips.platform.handbook import (
    HandbookClaim,
    HandbookDocument,
    render_html,
)


def test_html_export_is_deterministic_and_escapes_untrusted_content() -> None:
    document = HandbookDocument(
        schema_version=1,
        plan_revision_id="01991e28-1d65-7000-8000-000000000001",
        revision_number=1,
        claims=(
            HandbookClaim(
                text='<script>alert("owned")</script><img src=x onerror=alert(1)>',
                evidence_reference="fixture:lisbon:v1",
                observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            ),
        ),
    )

    first = render_html(document)
    second = render_html(document)

    assert first == second
    assert b"<script" not in first.lower()
    assert b"<img" not in first.lower()
    assert b"&lt;script&gt;" in first
    assert b"fixture:lisbon:v1" in first
