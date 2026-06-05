from __future__ import annotations

from pathlib import Path


def load_passwords(path: str | Path, include_blank: bool = True) -> list[str]:
    """Load a password list fresh from disk and deduplicate in order.

    This function intentionally reads the file every call so archive workers see newly added
    passwords before the next archive attempt.
    """
    password_path = Path(path)
    passwords: list[str] = []
    seen: set[str] = set()

    if password_path.exists():
        for raw_line in password_path.read_text(encoding="utf-8").splitlines():
            password = raw_line.strip()
            if password and password not in seen:
                seen.add(password)
                passwords.append(password)

    if include_blank and "" not in seen:
        passwords.append("")
    return passwords
