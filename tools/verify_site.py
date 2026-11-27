#!/usr/bin/env python3
"""Check the files produced by a Jekyll build using the Python standard library."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


REQUIRED_FILES = (
    "index.html",
    "assets/css/main.css",
    "assets/js/main.js",
    "images/profile.jpg",
    "sitemap.xml",
    "about/index.html",
    "about.html",
)


def verify_site(site_dir: Path) -> list[str]:
    """Report all required files and return every verification error."""
    errors: list[str] = []
    valid_files: set[str] = set()

    def report_error(relative_path: str, reason: str) -> None:
        message = f"{relative_path}: {reason}"
        errors.append(message)
        print(f"[ERROR] {message}")

    for relative_path in REQUIRED_FILES:
        output_path = site_dir / relative_path
        try:
            if not output_path.exists():
                report_error(relative_path, "missing file")
            elif not output_path.is_file():
                report_error(relative_path, "not a regular file")
            else:
                size = output_path.stat().st_size
                if size == 0:
                    report_error(relative_path, "empty file (0 bytes)")
                else:
                    valid_files.add(relative_path)
                    print(f"[OK] {relative_path} ({size} bytes)")
        except OSError as error:
            report_error(relative_path, f"cannot inspect file: {error}")

    css_relative_path = "assets/css/main.css"
    if css_relative_path in valid_files:
        try:
            css = (site_dir / css_relative_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            report_error(css_relative_path, f"cannot read CSS: {error}")
        else:
            if re.search(r"<!doctype|<html", css, flags=re.IGNORECASE):
                report_error(css_relative_path, "CSS output contains an HTML layout")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "site_dir",
        nargs="?",
        type=Path,
        default=Path("_site"),
        help="generated site directory (default: _site)",
    )
    site_dir = parser.parse_args().site_dir
    print(f"Verifying generated site: {site_dir.as_posix()}")
    errors = verify_site(site_dir)
    if errors:
        print(f"Verification failed: {len(errors)} error(s).")
        return 1

    print(f"Verification passed: {len(REQUIRED_FILES)} files; CSS contains no HTML layout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
