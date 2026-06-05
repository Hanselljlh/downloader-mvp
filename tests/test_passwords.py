from pathlib import Path

from vidgrab.archives.passwords import load_passwords


def test_load_passwords_hot_reloads_file_and_deduplicates(tmp_path: Path):
    password_file = tmp_path / "passwords.txt"
    password_file.write_text("alpha\n beta \nalpha\n\n", encoding="utf-8")

    assert load_passwords(password_file) == ["alpha", "beta", ""]

    password_file.write_text("gamma\nalpha\n", encoding="utf-8")

    assert load_passwords(password_file) == ["gamma", "alpha", ""]
