"""The README may not disagree with the measurements. This runs eval/check_claims.py
as a test so the disagreement fails the build instead of waiting to be noticed."""

import runpy
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[1] / "eval" / "check_claims.py"


def test_readme_matches_measurements(capsys):
    ns = runpy.run_path(str(CHECK), run_name="not_main")
    code = ns["main"]()
    out = capsys.readouterr().out
    assert code == 0, f"README and data disagree:\n{out}"
