from collections.abc import Callable
from typing import Any, cast

from fastapi import FastAPI


def install_problem_media_type(app: FastAPI) -> None:
    generated_openapi: Callable[[], dict[str, Any]] = app.openapi

    def openapi() -> dict[str, Any]:
        schema = generated_openapi()
        paths = cast(dict[str, object], schema["paths"])
        path_item = cast(dict[str, object], paths["/api/v1/status"])
        operation = cast(dict[str, object], path_item["get"])
        responses = cast(dict[str, object], operation["responses"])
        for status in ("404", "500"):
            problem_response = cast(dict[str, object], responses[status])
            content = cast(dict[str, object], problem_response["content"])
            content["application/problem+json"] = content.pop("application/json")
        return schema

    app.openapi = openapi
