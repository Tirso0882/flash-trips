import json
from pathlib import Path
from typing import Any, cast

from flash_trips.composition import create_app


def test_repeated_generation_keeps_the_problem_media_type() -> None:
    app = create_app()
    app.openapi()

    responses = app.openapi()["paths"]["/api/v1/status"]["get"]["responses"]

    assert set(responses["404"]["content"]) == {"application/problem+json"}


def test_committed_openapi_matches_the_pydantic_authored_contract() -> None:
    contract_path = Path("contracts/openapi/openapi.json")
    committed = cast(dict[str, Any], json.loads(contract_path.read_text()))

    assert committed == create_app().openapi()
    problem_schema = committed["components"]["schemas"]["ProblemResponse"]
    assert problem_schema["required"] == [
        "type",
        "title",
        "status",
        "detail",
        "code",
        "retryable",
        "request_id",
    ]
    assert problem_schema["properties"]["request_id"]["format"] == "uuid"
    responses = committed["paths"]["/api/v1/status"]["get"]["responses"]
    for status in ("404", "500"):
        assert responses[status]["content"] == {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemResponse"}
            }
        }

    assert committed["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "description": "Bearer access token",
        "scheme": "bearer",
    }
    principal_operation = committed["paths"]["/api/v1/authenticated-principal"]["get"]
    assert principal_operation["security"] == [{"BearerAuth": []}]
    for status in ("401", "403"):
        assert principal_operation["responses"][status]["content"] == {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemResponse"}
            }
        }

    start_run = committed["paths"]["/api/v1/trips/{trip_id}/runs"]["post"]
    assert start_run["operationId"] == "startRun"
    assert set(start_run["responses"]) == {
        "202",
        "401",
        "403",
        "404",
        "409",
        "422",
        "500",
    }
    assert start_run["responses"]["409"]["content"] == {
        "application/problem+json": {
            "schema": {"$ref": "#/components/schemas/ProblemResponse"}
        }
    }
    get_run = committed["paths"]["/api/v1/runs/{run_id}"]["get"]
    assert get_run["operationId"] == "getRun"
