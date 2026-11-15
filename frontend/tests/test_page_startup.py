"""A execução direta das páginas deve usar o inicializador da aplicação."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


FRONTEND = Path(__file__).resolve().parents[1]
ROOT = FRONTEND.parent


class PageStartupTest(unittest.TestCase):
    def test_direct_page_execution_launches_app_without_frontend_on_path(self):
        # Um processo novo reproduz o Run Python File do editor, sem os
        # imports e ajustes de sys.path feitos pelos outros testes.
        probe = r'''
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

page = Path(sys.argv[1]).resolve()
sys.argv = [str(page)]
sys.path[0] = str(page.parent)
frontend = page.parent.parent
assert str(frontend) not in sys.path
with patch("subprocess.call", return_value=0) as launch:
    try:
        runpy.run_path(str(page), run_name="__main__")
    except SystemExit as result:
        assert result.code == 0, result.code
    else:
        raise AssertionError("Page did not hand control to the launcher")
    launch.assert_called_once_with(
        [sys.executable, str(frontend.parent / "run.py")],
        cwd=frontend.parent,
    )
print("Page startup OK")
'''
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        for filename in ("1_Dashboard.py", "2_Activity.py", "3_Reports.py"):
            with self.subTest(page=filename):
                result = subprocess.run(
                    [sys.executable, "-c", probe, str(FRONTEND / "pages" / filename)],
                    cwd=ROOT, env=environment, capture_output=True, text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Page startup OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
