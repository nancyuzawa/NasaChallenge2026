"""Redireciona a execução direta do app para o iniciador do projeto."""

from pathlib import Path
import os
import subprocess
import sys


def launch_if_direct():
    root = Path(__file__).resolve().parent.parent
    interpreter = root / "frontend" / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    same_environment = Path(sys.executable).resolve() == interpreter.resolve()
    if same_environment:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
        except ImportError:
            pass
        else:
            if get_script_run_ctx(suppress_warning=True) is not None:
                return
    print("Iniciando pelo ambiente virtual do projeto...", flush=True)
    try:
        result = subprocess.call([sys.executable, str(root / "run.py"), *sys.argv[1:]], cwd=root)
    except KeyboardInterrupt:
        result = 0
    raise SystemExit(result)
