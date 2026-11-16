"""Catch renderer method mismatches against the actual bundled vendor API."""
from pathlib import Path
import shutil
import subprocess
import unittest


class GlobeRendererTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the renderer regression check")
    def test_renderer_initializes_with_bundled_api_and_original_palette(self):
        result = subprocess.run([shutil.which("node"),str(Path(__file__).with_name("globe_renderer_check.cjs"))],
                                capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn("sensors: OK",result.stdout)
