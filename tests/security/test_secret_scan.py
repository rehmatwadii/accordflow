import subprocess
import sys
from pathlib import Path


SCANNER = Path(__file__).resolve().parents[2] / "scripts" / "secret_scan.py"


def git(directory, *args):
    subprocess.run(["git", *args], cwd=directory, check=True, capture_output=True)


def test_scanner_reads_staged_bytes_and_redacts_secrets(tmp_path):
    git(tmp_path, "init")
    secret = "K" + "1" * 14
    sample = tmp_path / "sample.txt"
    sample.write_text(secret)
    git(tmp_path, "add", "sample.txt")
    sample.write_text("safe working tree; index still has the test credential")
    result = subprocess.run(
        [sys.executable, str(SCANNER), "--staged"], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "sample.txt" in result.stderr
    assert secret not in result.stderr + result.stdout


def test_scanner_accepts_blank_example_but_blocks_environment(tmp_path):
    git(tmp_path, "init")
    (tmp_path / ".env.example").write_text("OCR_SPACE_API_KEY=\n")
    git(tmp_path, "add", ".env.example")
    result = subprocess.run([sys.executable, str(SCANNER), "--staged"], cwd=tmp_path, capture_output=True)
    assert result.returncode == 0
    (tmp_path / ".env.production").write_text("PRIVATE_SETTING=value\n")
    git(tmp_path, "add", ".env.production")
    result = subprocess.run([sys.executable, str(SCANNER), "--staged"], cwd=tmp_path, capture_output=True)
    assert result.returncode != 0
