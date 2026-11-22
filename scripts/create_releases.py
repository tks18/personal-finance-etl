#!/usr/bin/env python3
# ruff: noqa
# type: ignore
# pylint: skip-file
# flake8: noqa
"""Module to parse CHANGELOG.md and publish GitHub releases."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    reconfig_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig_out):
        reconfig_out(encoding="utf-8", errors="replace")
    reconfig_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfig_err):
        reconfig_err(encoding="utf-8", errors="replace")


def get_project_root() -> Path:
    """Finds project root by inspecting parents of this file for pyproject.toml."""
    current = Path(__file__).resolve().parent
    for p in [current, *current.parents]:
        if (p / "pyproject.toml").exists() or (p / "CHANGELOG.md").exists():
            return p
    return current.parent


def get_existing_git_tags(repo_dir: Path) -> set[str]:
    """Fetch all git tags from repository root."""
    try:
        result = subprocess.run(
            ["git", "tag"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return set(result.stdout.strip().splitlines())
    except subprocess.CalledProcessError as e:
        print(f"Error fetching git tags: {e}")
        sys.exit(1)


def parse_changelog(filepath: Path) -> list[dict[str, str]]:
    content = filepath.read_text(encoding="utf-8")

    header_pattern = re.compile(
        r"^#{2,3}\s+(?:\[(?P<ver_bracket>v?\d+\.\d+\.\d+[^\s\]]*)\]|(?P<ver_plain>v?\d+\.\d+\.\d+[^\s\(]*))",
        re.MULTILINE,
    )

    matches = list(header_pattern.finditer(content))
    releases = []

    for i, match in enumerate(matches):
        version = (match.group("ver_bracket") or match.group("ver_plain")).strip()
        start_idx = match.start()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)

        raw_body = content[start_idx:end_idx].strip()
        body = "## " + raw_body[4:] if raw_body.startswith("### ") else raw_body

        releases.append({"version": version, "body": body})

    return releases


def resolve_git_tag(version: str, existing_tags: set[str]) -> str | None:
    clean_ver = version.lstrip("v")
    for candidate in [clean_ver, f"v{clean_ver}"]:
        if candidate in existing_tags:
            return candidate
    return None


def print_release_preview(tag: str, title: str, body: str, index: int, total: int):
    separator = "=" * 80
    print(f"\n{separator}")
    print(f"[{index}/{total}] PREVIEW: {tag}")
    print(f"{separator}")
    print(f"• Target Git Tag   : {tag}")
    print(f"• Release Title    : {title}")
    print(f"• Release Content  :\n")
    print(body)
    print(f"{separator}\n")


def publish_release(repo_dir: Path, tag: str, title: str, body: str, is_draft: bool = False):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        f.write(body)
        temp_notes_file = f.name

    cmd = [
        "gh",
        "release",
        "create",
        tag,
        "--title",
        title,
        "--notes-file",
        temp_notes_file,
    ]
    if is_draft:
        cmd.append("--draft")

    try:
        subprocess.run(cmd, cwd=repo_dir, check=True)
        print(f"✔ Successfully released {tag}{' (as draft)' if is_draft else ''}")
    except subprocess.CalledProcessError as e:
        print(f"✘ Failed to create release for {tag}: {e}")
    finally:
        Path(temp_notes_file).unlink(missing_ok=True)


def run_release_cli(cli_args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="poe release",
        description="Release manager: publish historical or latest tags with changelog to GitHub",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute release creation on GitHub (dry-run if omitted)",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Automatically pick the most recent/top version from CHANGELOG.md",
    )
    parser.add_argument(
        "--single",
        type=str,
        metavar="VERSION",
        help="Target a specific version to release (e.g., --single 8.2.0)",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Create release as a Draft on GitHub (safe testing)",
    )
    parser.add_argument(
        "--preview",
        nargs="?",
        const="LATEST",  # Defaults to latest if --preview is passed without a version
        metavar="VERSION",
        help="Preview full notes. Pass a version (e.g., --preview 8.1.1) or leave blank/combine with --latest for newest",
    )
    parser.add_argument(
        "--preview-all",
        action="store_true",
        help="Display the full content preview for all releases",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for confirmation [y/n/q/all] before publishing each tag",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to CHANGELOG.md (defaults to project root / CHANGELOG.md)",
    )

    args = parser.parse_args(cli_args)
    root_dir = get_project_root()
    changelog_path = Path(args.file) if args.file else (root_dir / "CHANGELOG.md")

    if not changelog_path.exists():
        print(f"Error: Changelog file not found at '{changelog_path.resolve()}'")
        return 1

    existing_tags = get_existing_git_tags(root_dir)
    releases = parse_changelog(changelog_path)

    if not releases:
        print(f"Error: No releases could be parsed from {changelog_path.name}.")
        return 1

    # 1. Preview Single / Latest Version
    if args.preview is not None or (args.latest and not args.run and not args.preview_all):
        # Determine whether to preview 'latest' or a specific version
        if args.preview in (None, "LATEST") or args.latest:
            entry = releases[0]
            print(f"[*] Previewing latest version in changelog: v{entry['version'].lstrip('v')}")
        else:
            target_version = args.preview.lstrip("v")
            entry = next((r for r in releases if r["version"].lstrip("v") == target_version), None)
            if not entry:
                print(f"Version '{args.preview}' not found in {changelog_path.name}.")
                return 1

        tag = (
            resolve_git_tag(entry["version"], existing_tags)
            or f"{entry['version']} (TAG NOT IN GIT)"
        )
        title = f"Release - v{entry['version'].lstrip('v')}"
        print_release_preview(tag, title, entry["body"], 1, 1)
        return 0

    # 2. Preview All
    if args.preview_all:
        for idx, rel in enumerate(releases, 1):
            tag = (
                resolve_git_tag(rel["version"], existing_tags)
                or f"{rel['version']} (TAG NOT IN GIT)"
            )
            title = f"Release - v{rel['version'].lstrip('v')}"
            print_release_preview(tag, title, rel["body"], idx, len(releases))
        return 0

    # 3. Handle --latest for publishing
    if args.latest:
        latest_entry = releases[0]
        print(f"[*] Selected latest version in changelog: v{latest_entry['version'].lstrip('v')}")
        releases = [latest_entry]

    # 4. Handle --single for publishing
    elif args.single:
        target = args.single.lstrip("v")
        releases = [r for r in releases if r["version"].lstrip("v") == target]
        if not releases:
            print(f"Version '{args.single}' not found in {changelog_path.name}.")
            return 1

    # Match targets against local git tags
    valid_releases = []
    for rel in releases:
        tag = resolve_git_tag(rel["version"], existing_tags)
        if tag:
            valid_releases.append((tag, rel))
        else:
            print(f"[!] Warning: Git tag for version '{rel['version']}' not found. Skipping.")

    total_valid = len(valid_releases)
    if total_valid == 0:
        print("No matching git tags found to release.")
        return 0

    # Dry-Run Summary (only reaches here if --run is not passed and neither preview mode was triggered)
    if not args.run:
        print(f"\n[DRY RUN] Found {total_valid} release(s) ready in {changelog_path.name}:")
        for idx, (tag, rel) in enumerate(valid_releases, 1):
            title = f"Release - v{rel['version'].lstrip('v')}"
            first_line = rel["body"].splitlines()[0] if rel["body"] else ""
            print(
                f"[{idx:02d}/{total_valid:02d}] Tag: {tag:<10} | Title: {title:<20} | Starts: {first_line[:40]}..."
            )
        print("\nPass '--run' to publish. You can combine with '--draft' to test on GitHub first.")
        return 0

    # Publish Execution
    for idx, (tag, rel) in enumerate(valid_releases, 1):
        title = f"Release - v{rel['version'].lstrip('v')}"
        body = rel["body"]

        if args.interactive:
            print_release_preview(tag, title, body, idx, total_valid)
            choice = input(f"Publish release for tag '{tag}'? [y/n/q/all]: ").strip().lower()
            if choice == "q":
                break
            elif choice == "n":
                continue
            elif choice == "all":
                args.interactive = False

        print(f"Publishing release [{idx}/{total_valid}] -> Tag '{tag}', Title '{title}'...")
        publish_release(root_dir, tag, title, body, is_draft=args.draft)

    return 0


if __name__ == "__main__":
    sys.exit(run_release_cli())
