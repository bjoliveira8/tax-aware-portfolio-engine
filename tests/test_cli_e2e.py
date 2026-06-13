import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_end_to_end(tmp_path: Path):
    output = tmp_path / "portfolio_report.md"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "analyze",
            "--holdings",
            str(ROOT / "data/mock_holdings.csv"),
            "--lots",
            str(ROOT / "data/mock_tax_lots.csv"),
            "--account-menus",
            str(ROOT / "data/mock_account_menus.csv"),
            "--security-master",
            str(ROOT / "data/security_master.csv"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Total value:" in result.stdout
    assert output.exists()
    report = output.read_text(encoding="utf-8")
    assert "BOTTOM LINE" in report
