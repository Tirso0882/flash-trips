import os
import shutil
import subprocess
from pathlib import Path


def run_import_linter(project: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project / "src")
    executable = shutil.which("lint-imports")
    assert executable is not None
    return subprocess.run(
        [executable, "--config", str(project / ".importlinter"), "--no-cache"],
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_repository_import_boundaries_are_satisfied() -> None:
    result = run_import_linter(Path.cwd())

    assert result.returncode == 0, result.stdout + result.stderr


def test_kernel_importing_application_is_rejected(tmp_path: Path) -> None:
    shutil.copytree("src", tmp_path / "src")
    shutil.copy(".importlinter", tmp_path / ".importlinter")
    violation = tmp_path / "src/flash_trips/kernel/forbidden_dependency.py"
    violation.write_text(
        "from flash_trips.application import TripPlanning\n",
        encoding="utf-8",
    )

    result = run_import_linter(tmp_path)

    assert result.returncode == 1
    assert "Kernel is independent" in result.stdout
    assert "flash_trips.kernel is not allowed to import flash_trips.application" in (
        result.stdout
    )


def test_application_importing_framework_is_rejected(tmp_path: Path) -> None:
    shutil.copytree("src", tmp_path / "src")
    shutil.copy(".importlinter", tmp_path / ".importlinter")
    violation = tmp_path / "src/flash_trips/application/forbidden_framework.py"
    violation.write_text("from fastapi import FastAPI\n", encoding="utf-8")

    result = run_import_linter(tmp_path)

    assert result.returncode == 1
    assert "Application does not depend on adapters or composition" in result.stdout
    assert "flash_trips.application is not allowed to import fastapi" in result.stdout


def test_capability_importing_framework_is_rejected(tmp_path: Path) -> None:
    shutil.copytree("src", tmp_path / "src")
    shutil.copy(".importlinter", tmp_path / ".importlinter")
    violation = (
        tmp_path / "src/flash_trips/capabilities/trip_request/forbidden_framework.py"
    )
    violation.write_text("from fastapi import FastAPI\n", encoding="utf-8")

    result = run_import_linter(tmp_path)

    assert result.returncode == 1
    assert "Capabilities do not depend on application adapters or composition" in (
        result.stdout
    )
    assert "flash_trips.capabilities is not allowed to import fastapi" in result.stdout


def test_capability_importing_application_is_rejected(tmp_path: Path) -> None:
    shutil.copytree("src", tmp_path / "src")
    shutil.copy(".importlinter", tmp_path / ".importlinter")
    violation = (
        tmp_path / "src/flash_trips/capabilities/trip_request/forbidden_application.py"
    )
    violation.write_text(
        "from flash_trips.application import TripPlanning\n",
        encoding="utf-8",
    )

    result = run_import_linter(tmp_path)

    assert result.returncode == 1
    assert "Capabilities do not depend on application adapters or composition" in (
        result.stdout
    )
    assert (
        "flash_trips.capabilities is not allowed to import flash_trips.application"
        in result.stdout
    )


def test_kernel_capability_contract_is_importable_from_both_sides(
    tmp_path: Path,
) -> None:
    shutil.copytree("src", tmp_path / "src")
    shutil.copy(".importlinter", tmp_path / ".importlinter")
    import_statement = "from flash_trips.kernel.capability import Capability\n"
    (tmp_path / "src/flash_trips/application/kernel_contract_consumer.py").write_text(
        import_statement, encoding="utf-8"
    )
    (
        tmp_path
        / "src/flash_trips/capabilities/trip_request/kernel_contract_consumer.py"
    ).write_text(import_statement, encoding="utf-8")

    result = run_import_linter(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_adapter_importing_capability_internal_is_rejected(tmp_path: Path) -> None:
    shutil.copytree("src", tmp_path / "src")
    shutil.copy(".importlinter", tmp_path / ".importlinter")
    internal = tmp_path / "src/flash_trips/capabilities/trip_request/_implementation.py"
    internal.write_text("VALUE = 1\n", encoding="utf-8")
    violation = tmp_path / "src/flash_trips/adapters/forbidden_internal.py"
    violation.write_text(
        "from flash_trips.capabilities.trip_request._implementation import VALUE\n",
        encoding="utf-8",
    )

    result = run_import_linter(tmp_path)

    assert result.returncode == 1
    assert "Capability internals are protected" in result.stdout
