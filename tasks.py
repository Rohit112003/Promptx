"""Cross-platform task runner (works where `make` is unavailable, e.g. Windows).

    python tasks.py <target>

Targets: setup, chain, deploy, backend, test, seed, demo
Mirrors the Makefile so the same workflow runs on any OS.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WIN = platform.system() == "Windows"
VENV_PY = ROOT / ".venv" / ("Scripts" if IS_WIN else "bin") / ("python.exe" if IS_WIN else "python")


def py() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, check: bool = True):
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd or ROOT), env=env, check=check, shell=False)


def npm(*args: str) -> list[str]:
    return (["npm.cmd", *args] if IS_WIN else ["npm", *args])


def npx(*args: str) -> list[str]:
    return (["npx.cmd", *args] if IS_WIN else ["npx", *args])


# ---- targets ----
def setup() -> None:
    run(npm("install", "--no-audit", "--no-fund"))
    if not VENV_PY.exists():
        run([sys.executable, "-m", "venv", ".venv"])
    run([py(), "-m", "pip", "install", "-U", "pip"])
    run([py(), "-m", "pip", "install", "-r", "requirements.txt"])
    run(npx("hardhat", "compile"))
    run(["node", "scripts/export-artifact.js"])
    print("\nSetup complete. Try:  python tasks.py demo")


def chain() -> None:
    run(npx("hardhat", "node"))


def deploy() -> None:
    run(npx("hardhat", "run", "scripts/deploy.js", "--network", "localhost"))


def backend() -> None:
    run([py(), "-m", "app"], cwd=ROOT / "backend")


def test() -> None:
    run(npx("hardhat", "test"))
    run([py(), "-m", "pytest", "-q"], cwd=ROOT / "backend")


def seed() -> None:
    run([py(), "backend/scripts/seed_demo_data.py"])


def demo() -> None:
    """Start the backend (inmemory), wait for health, seed, then keep serving."""
    import httpx

    env = {**os.environ, "CHAIN_MODE": os.environ.get("CHAIN_MODE", "inmemory"),
           "DB_MODE": os.environ.get("DB_MODE", "sqlite")}
    proc = subprocess.Popen([py(), "-m", "app"], cwd=str(ROOT / "backend"), env=env)
    try:
        base = "http://localhost:8000/api/v1/health"
        for _ in range(60):
            try:
                if httpx.get(base, timeout=2).status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("Backend failed to start", file=sys.stderr)
            proc.terminate()
            sys.exit(1)
        run([py(), "backend/scripts/seed_demo_data.py"], env=env)
        print("\n" + "=" * 60)
        print("  Demo ready!  Swagger UI: http://localhost:8000/docs")
        print("  Login: admin / agent / custodian / auditor / investor1..5")
        print("  Password: demo")
        print("  Press Ctrl+C to stop.")
        print("=" * 60)
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


TARGETS = {
    "setup": setup, "chain": chain, "deploy": deploy, "backend": backend,
    "test": test, "seed": seed, "demo": demo,
}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in TARGETS:
        print(f"Usage: python tasks.py <{'|'.join(TARGETS)}>")
        sys.exit(2)
    TARGETS[sys.argv[1]]()
