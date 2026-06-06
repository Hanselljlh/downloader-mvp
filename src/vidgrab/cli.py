from __future__ import annotations

import argparse
from pathlib import Path

from vidgrab.archives.passwords import load_passwords
from vidgrab.linkgrabber import categorize_url, extract_urls_from_clipboard_text


def main() -> int:
    parser = argparse.ArgumentParser(prog="vidgrab")
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan = subcommands.add_parser("scan-text", help="Extract and categorize URLs from copied text/HTML")
    scan.add_argument("path", type=Path, help="Text file containing copied browser/page content")

    passwords = subcommands.add_parser("passwords", help="Load password list as the archive worker would")
    passwords.add_argument("path", type=Path)

    subcommands.add_parser("gui", help="Launch the portable desktop LinkGrabber shell")

    args = parser.parse_args()
    if args.command == "scan-text":
        for url in extract_urls_from_clipboard_text(args.path.read_text(encoding="utf-8")):
            print(f"{categorize_url(url):10} {url}")
        return 0
    if args.command == "passwords":
        for password in load_passwords(args.path):
            label = "<blank>" if password == "" else "*" * len(password)
            print(label)
        return 0
    if args.command == "gui":
        from vidgrab.desktop import run_desktop_app

        return run_desktop_app()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
