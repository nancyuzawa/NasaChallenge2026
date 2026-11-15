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
    # O Streamlit já estará carregado quando estiver executando uma página.
    # Na execução direta, deixe a preparação das dependências para run.py.
    if same_environment and "streamlit" in sys.modules:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
        except ImportError:
            pass
        else:
            if get_script_run_ctx(suppress_warning=True) is not None:
                return
    print("Starting with the project's virtual environment...", flush=True)
    try:
        result = subprocess.call([sys.executable, str(root / "run.py"), *sys.argv[1:]], cwd=root)
    except KeyboardInterrupt:
        result = 0
    raise SystemExit(result)
