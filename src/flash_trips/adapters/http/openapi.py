from collections.abc import Callable
from typing import Any, cast

from fastapi import FastAPI

_PROBLEM_STATUSES = ("401", "403", "404", "500")
_OPERATION_METHODS = ("delete", "get", "patch", "post", "put")


def _use_problem_media_type(operation: dict[str, Any]) -> None:
    responses = cast(dict[str, Any], operation["responses"])
    for status in _PROBLEM_STATUSES:
        if status not in responses:
            continue
        content = cast(dict[str, Any], responses[status]["content"])
        # FastAPI caches the document, so every later call sees the rewritten copy.
        if "application/json" in content:
            content["application/problem+json"] = content.pop("application/json")


def install_problem_media_type(app: FastAPI) -> None:
    generated_openapi: Callable[[], dict[str, Any]] = app.openapi

    def openapi() -> dict[str, Any]:
        schema = generated_openapi()
        paths = cast(dict[str, dict[str, Any]], schema["paths"])
        for path_item in paths.values():
            for method in _OPERATION_METHODS:
                if method in path_item:
                    _use_problem_media_type(cast(dict[str, Any], path_item[method]))
        return schema

    app.openapi = openapi
