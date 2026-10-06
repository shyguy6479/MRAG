"""Start the API and Vite together, stop both on Ctrl-C, and fail on either exit."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    processes: list[subprocess.Popen[bytes]] = []
    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "apps.api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--reload",
                ],
                cwd=root,
                env=env,
            )
        )
        processes.append(
            subprocess.Popen(
                ["npm", "run", "dev", "--", "--port", "5173", "--strictPort"],
                cwd=root / "apps/web",
                env=env,
            )
        )
        print("MRAG: http://127.0.0.1:5173 — Ctrl-C stops both servers.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.3)
        if any(process.returncode for process in processes):
            raise SystemExit("A server stopped; inspect the error above.")
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()


if __name__ == "__main__":
    main()
