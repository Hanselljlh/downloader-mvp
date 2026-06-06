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

    extract = subcommands.add_parser(
        "extract-archive",
        help="Run the archive extraction worker against a single archive and password file",
    )
    extract.add_argument("archive", type=Path, help="Archive file to extract (.zip, .7z, .rar, …)")
    extract.add_argument("password_file", type=Path, help="Password list file (one password per line)")
    extract.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: archive stem next to the archive)",
    )
    extract.add_argument("--binary", default="7zz", help="Path/name of the 7zz binary (default: 7zz)")

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
    if args.command == "extract-archive":
        return _cmd_extract_archive(args)
    return 1


def _cmd_extract_archive(args: argparse.Namespace) -> int:
    from vidgrab.archives.extractor import ArchiveWorker

    archive: Path = args.archive
    output: Path = args.output or archive.parent / archive.stem
    worker = ArchiveWorker(args.password_file, binary=args.binary)
    result = worker.process(archive, output)
    if result.success:
        print(f"Extracted to: {result.extracted_to}")
        return 0
    print(f"Failed: {result.error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
