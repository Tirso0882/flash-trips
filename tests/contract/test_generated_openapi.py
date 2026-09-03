import json
from pathlib import Path
from typing import Any, cast

from flash_trips.composition import create_app


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
