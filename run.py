"""Prepare the frontend environment and start Streamlit with its Python interpreter."""

import argparse
import hashlib
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import venv


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
ENVIRONMENT = FRONTEND / ".venv"
PYTHON = ENVIRONMENT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUIREMENTS = FRONTEND / "requirements.txt"
STAMP = ENVIRONMENT / ".requirements.sha256"
IMPORT_CHECK = "import streamlit; import plotly.graph_objects; import numpy; import pandas"


def run(command, **kwargs):
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def install_dependencies():
    """Usa as CAs confiáveis do Windows, preservando a validação HTTPS."""
    environment = os.environ.copy()
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    with tempfile.TemporaryDirectory(prefix="firewatch-ca-") as directory:
        if os.name == "nt" and not environment.get("PIP_CERT"):
            certificates = []
            for store in ("ROOT", "CA"):
                for certificate, encoding, trust in ssl.enum_certificates(store):
                    if encoding == "x509_asn" and (
                        trust is True or ssl.Purpose.SERVER_AUTH.oid in trust
                    ):
                        certificates.append(ssl.DER_cert_to_PEM_cert(certificate))
            if certificates:
                bundle = Path(directory) / "windows-ca.pem"
                bundle.write_text("\n".join(certificates), encoding="ascii")
                environment["PIP_CERT"] = str(bundle)
        print("Installing dependencies in frontend/.venv...", flush=True)
        run([str(PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)], env=environment)


def prepare_environment(force_install=False):
    if not PYTHON.exists():
        print("Creating the virtual environment in frontend/.venv...", flush=True)
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)
    fingerprint = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    recorded = STAMP.read_text(encoding="ascii").strip() if STAMP.exists() else ""
    # Importa os pacotes de fato: encontrar apenas o nome não detecta uma instalação incompleta.
    probe = subprocess.run([str(PYTHON), "-c", IMPORT_CHECK], cwd=ROOT, capture_output=True, text=True)
    compatibility = subprocess.run(
        [str(PYTHON), "-m", "pip", "check"], cwd=ROOT, capture_output=True, text=True
    )
    if force_install or probe.returncode or compatibility.returncode or recorded != fingerprint:
        install_dependencies()
    run([str(PYTHON), "-c", IMPORT_CHECK])
    run([str(PYTHON), "-m", "pip", "check"])
    STAMP.write_text(fingerprint, encoding="ascii")
    print(f"Application Python: {PYTHON}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Prepare and verify dependencies without starting the app.")
    parser.add_argument("--install", action="store_true", help="Reinstall the declared dependencies.")
    options, streamlit_options = parser.parse_known_args()
    try:
        prepare_environment(force_install=options.install)
        if options.check:
            print("Streamlit, Plotly, NumPy, pandas, and dependencies are ready.", flush=True)
            return 0
        return subprocess.call(
            [str(PYTHON), "-m", "streamlit", "run", str(FRONTEND / "app.py"), *streamlit_options],
            cwd=FRONTEND,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Could not prepare or start the application: {error}", file=sys.stderr)
        print("Check the details above. To retry installation: python run.py --install", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
