"""Unit tests for automated release tooling, SemVer to PEP 440 bridging, and pre-release pipelines.

Owns
----
- Verification of SemVer 2.0.0 and PEP 440 bi-directional conversion.
- Validation of Windows PE resource (version_info.txt) 4-integer tuple parsing.
- Verification of pre-release tag detection in GitHub release and PR scripts.
- Integrity verification of current version_info.txt, pyproject.toml, and package.json.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest
from scripts.create_pr import format_audit_markdown
from scripts.create_pr import is_prerelease as is_prerelease_pr
from scripts.create_releases import format_release_title
from scripts.create_releases import is_prerelease as is_prerelease_rel
from scripts.release_bump import calculate_next_versions, get_current_version


@pytest.fixture
def repo_root() -> Path:
    """Fixture providing repository root path."""
    return Path(__file__).resolve().parent.parent.parent


def test_is_prerelease_detection() -> None:
    """Verify pre-release detection accurately identifies RC, alpha, beta, and stable versions."""
    # Pre-release cases (SemVer and PEP 440)
    prerelease_cases = [
        "10.0.0-rc.1",
        "10.0.0-rc.10",
        "10.0.0rc1",
        "10.0.0rc10",
        "10.0.0-alpha.1",
        "10.0.0a1",
        "10.0.0-beta.2",
        "10.0.0b2",
        "v10.0.0-rc.1",
        "v10.0.0rc2",
        "10.0.0-dev.1",
        "10.0.0-preview.1",
    ]
    for case in prerelease_cases:
        assert is_prerelease_rel(case) is True, (
            f"Failed to identify {case} as pre-release in create_releases"
        )
        assert is_prerelease_pr(case) is True, (
            f"Failed to identify {case} as pre-release in create_pr"
        )

    # Production / Stable cases
    stable_cases = [
        "9.9.6",
        "v9.9.6",
        "10.0.0",
        "v10.0.0",
        "1.2.3",
        "8.0.0",
    ]
    for case in stable_cases:
        assert is_prerelease_rel(case) is False, (
            f"Incorrectly marked {case} as pre-release in create_releases"
        )
        assert is_prerelease_pr(case) is False, (
            f"Incorrectly marked {case} as pre-release in create_pr"
        )


def test_format_release_title() -> None:
    """Verify release title formatting differentiates pre-releases and production releases."""
    assert format_release_title("10.0.0-rc.1") == "Pre-Release - v10.0.0-rc.1"
    assert format_release_title("v10.0.0-rc.2") == "Pre-Release - v10.0.0-rc.2"
    assert format_release_title("10.0.0rc1") == "Pre-Release - v10.0.0rc1"
    assert format_release_title("9.9.6") == "Release - v9.9.6"
    assert format_release_title("v10.0.0") == "Release - v10.0.0"


def test_format_audit_markdown() -> None:
    """Verify audit markdown table includes appropriate release track badges."""
    sample_audit: dict[str, object] = {
        "timestamp": "2026-11-16T15:00:00",
        "all_passed": True,
        "total_duration_seconds": 12.34,
        "engines": [
            {
                "name": "Ruff Check",
                "tier": "Fast",
                "duration_seconds": 0.1,
                "issue_count": 0,
                "passed": True,
            }
        ],
    }

    # Stable release PR
    md_stable = format_audit_markdown(sample_audit, "dev", "master", is_pre=False)
    assert "🚀 **Production Stable Track**" in md_stable
    assert "🟢 **ALL QUALITY ENGINES PASSED**" in md_stable

    # Pre-release PR
    md_pre = format_audit_markdown(sample_audit, "dev", "master", is_pre=True)
    assert "🧪 **Pre-Release Track (Release Candidate)**" in md_pre
    assert "🟢 **ALL QUALITY ENGINES PASSED**" in md_pre


def test_javascript_python_updater(repo_root: Path) -> None:
    """Verify python.js updater correctly performs bi-directional version conversions via Node.js."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not available in the test environment.")

    updater_path = repo_root / "scripts" / "updaters" / "python.js"
    assert updater_path.exists(), "python.js updater script must exist"

    test_script = f"""
    const py = require('{updater_path.as_posix()}');
    const results = {{
        toPython: {{
            rc1: py.toPythonVersion('10.0.0-rc.1'),
            rc10: py.toPythonVersion('10.0.0-rc.10'),
            alpha1: py.toPythonVersion('10.0.0-alpha.1'),
            beta2: py.toPythonVersion('10.0.0-beta.2'),
            stable: py.toPythonVersion('10.0.0'),
            current: py.toPythonVersion('9.9.6'),
        }},
        toSemver: {{
            rc1: py.toSemver('10.0.0rc1'),
            rc10: py.toSemver('10.0.0rc10'),
            alpha1: py.toSemver('10.0.0a1'),
            beta2: py.toSemver('10.0.0b2'),
            stable: py.toSemver('10.0.0'),
            current: py.toSemver('9.9.6'),
        }}
    }};
    console.log(JSON.stringify(results));
    """

    res = subprocess.run(
        [node_exe, "-"], input=test_script, capture_output=True, text=True, check=True
    )
    assert res.stdout.strip(), f"Node execution produced no output. Stderr: {res.stderr}"
    data = json.loads(res.stdout.strip())

    assert data["toPython"]["rc1"] == "10.0.0rc1"
    assert data["toPython"]["rc10"] == "10.0.0rc10"
    assert data["toPython"]["alpha1"] == "10.0.0a1"
    assert data["toPython"]["beta2"] == "10.0.0b2"
    assert data["toPython"]["stable"] == "10.0.0"
    assert data["toPython"]["current"] == "9.9.6"

    assert data["toSemver"]["rc1"] == "10.0.0-rc.1"
    assert data["toSemver"]["rc10"] == "10.0.0-rc.10"
    assert data["toSemver"]["alpha1"] == "10.0.0-alpha.1"
    assert data["toSemver"]["beta2"] == "10.0.0-beta.2"
    assert data["toSemver"]["stable"] == "10.0.0"
    assert data["toSemver"]["current"] == "9.9.6"


def test_javascript_version_info_updater(repo_root: Path) -> None:
    """Verify version_info.js updater correctly formats 4-integer tuples and StringStructs."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not available in the test environment.")

    updater_path = repo_root / "scripts" / "updaters" / "version_info.js"
    assert updater_path.exists(), "version_info.js updater script must exist"

    test_script = f"""
    const vi = require('{updater_path.as_posix()}');
    const dummyContents = `
        filevers=(9, 9, 6, 0),
        prodvers=(9, 9, 6, 0),
        StringStruct('FileVersion', '9.9.6')
        StringStruct('ProductVersion', '9.9.6')
    `;
    const updated = vi.writeVersion(dummyContents, '10.0.0-rc.1');
    const results = {{
        tuple_stable: vi.parseVersionTuple('10.0.0'),
        tuple_rc1: vi.parseVersionTuple('10.0.0-rc.1'),
        tuple_rc10: vi.parseVersionTuple('10.0.0-rc.10'),
        updatedContents: updated
    }};
    console.log(JSON.stringify(results));
    """

    res = subprocess.run(
        [node_exe, "-"], input=test_script, capture_output=True, text=True, check=True
    )
    assert res.stdout.strip(), f"Node execution produced no output. Stderr: {res.stderr}"
    data = json.loads(res.stdout.strip())

    assert data["tuple_stable"] == "10, 0, 0, 0"
    assert data["tuple_rc1"] == "10, 0, 0, 1"
    assert data["tuple_rc10"] == "10, 0, 0, 10"

    updated_text = data["updatedContents"]
    assert "filevers=(10, 0, 0, 1)" in updated_text
    assert "prodvers=(10, 0, 0, 1)" in updated_text
    assert "StringStruct('FileVersion', '10.0.0-rc.1')" in updated_text
    assert "StringStruct('ProductVersion', '10.0.0-rc.1')" in updated_text


def test_version_info_txt_format(repo_root: Path) -> None:
    """Verify repository version_info.txt adheres to PyInstaller 4-integer tuple requirement."""
    version_info_path = repo_root / "version_info.txt"
    assert version_info_path.exists(), "version_info.txt must exist at repository root"

    content = version_info_path.read_text(encoding="utf-8")
    filevers_match = re.search(r"filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", content)
    prodvers_match = re.search(r"prodvers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", content)

    assert filevers_match is not None, "filevers must strictly be a 4-integer tuple"
    assert prodvers_match is not None, "prodvers must strictly be a 4-integer tuple"


def test_dynamic_release_bump_projections(repo_root: Path) -> None:
    """Verify calculate_next_versions accurately projects future major, minor, patch, and RC tracks."""
    # From stable 9.9.6 (starts pre-release index at 1)
    proj_stable = calculate_next_versions("9.9.6")
    assert proj_stable["major"] == "10.0.0"
    assert proj_stable["minor"] == "9.10.0"
    assert proj_stable["patch"] == "9.9.7"
    assert proj_stable["major_rc"] == "10.0.0-rc.1"
    assert proj_stable["minor_rc"] == "9.10.0-rc.1"
    assert proj_stable["patch_rc"] == "9.9.7-rc.1"
    assert "current_pre_inc" not in proj_stable

    # From pre-release 10.0.0-rc.2
    proj_pre = calculate_next_versions("10.0.0-rc.2")
    assert proj_pre["current_pre_inc"] == "10.0.0-rc.3"
    assert proj_pre["promote_stable"] == "10.0.0"

    # From pre-release 11.2.0-beta.0
    proj_beta = calculate_next_versions("11.2.0-beta.0")
    assert proj_beta["current_pre_inc"] == "11.2.0-beta.1"
    assert proj_beta["promote_stable"] == "11.2.0"

    current = get_current_version(repo_root)
    assert re.match(r"^\d+\.\d+\.\d+", current) is not None


def test_package_json_has_no_hardcoded_versions(repo_root: Path) -> None:
    """Verify package.json scripts contain no hardcoded version strings."""
    pkg_path = repo_root / "package.json"
    data = cast(dict[str, object], json.loads(pkg_path.read_text(encoding="utf-8")))
    scripts = cast(dict[str, str], data.get("scripts", {}))

    for script_name, cmd in scripts.items():
        # Check that no script hardcodes a specific version like 10.0.0 or 10.0.0-rc.1
        hardcoded_match = re.search(r"--release-as\s+\d+\.\d+\.\d+", cmd)
        assert hardcoded_match is None, (
            f"Script '{script_name}' hardcodes release-as version: '{cmd}'. "
            "All release scripts must be dynamically parameterized."
        )
