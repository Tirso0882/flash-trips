import json

import pytest

from flash_trips.adapters.telemetry import configure_logging


def test_structured_logging_redacts_sensitive_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    logger = configure_logging()

    logger.info(
        "dependency_check",
        extra={
            "request_id": "request-123",
            "token": "secret-token",
            "trip_content": "private itinerary",
            "destination": "private destination",
            "budget": "private budget",
        },
    )

    captured = capsys.readouterr()
    record = json.loads(captured.err)
    assert record == {
        "event": "dependency_check",
        "level": "INFO",
        "request_id": "request-123",
        "budget": "[REDACTED]",
        "destination": "[REDACTED]",
        "token": "[REDACTED]",
        "trip_content": "[REDACTED]",
    }


def test_log_message_cannot_carry_interpolated_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    logger = configure_logging()

    logger.info("token=%s", "secret-token")

    captured = capsys.readouterr()
    record = json.loads(captured.err)
    assert record["event"] == "invalid_event_name"
    assert "secret-token" not in captured.err
