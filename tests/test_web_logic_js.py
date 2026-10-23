"""S11: run the page's JavaScript tests (tests/js/) under several browser time zones.

Needs Node.js 20+. Skipped, with a reason, on machines without it.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
TEST_FILE = Path(__file__).parent / "js" / "logic.test.mjs"


@pytest.mark.skipif(NODE is None, reason="Node.js not installed; JavaScript tests not run")
@pytest.mark.parametrize(
    "browser_tz", ["UTC", "America/New_York", "Asia/Tokyo", "Pacific/Auckland"]
)
def test_page_logic(browser_tz):
    result = subprocess.run(
        [NODE, "--test", str(TEST_FILE)],
        env={"TZ": browser_tz, "PATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
