"""
Runs main.py on every file in samples/invoices/, then runs eval.py once at the end.
Usage: python run_batch.py
"""
import os
import subprocess
import sys
from pathlib import Path

SAMPLES_DIR = Path(__file__).parent / "samples" / "invoices"

ENV = os.environ.copy()
ENV["PYTHONIOENCODING"] = "utf-8"


def main():
    files = sorted([f for f in SAMPLES_DIR.iterdir() if f.is_file()])
    if not files:
        print(f"No files found in {SAMPLES_DIR}")
        return

    ok, failed = [], []
    print(f"Processing {len(files)} file(s)...\n")

    for f in files:
        result = subprocess.run(
            [sys.executable, "main.py", str(f)],
            capture_output=True, text=True, encoding="utf-8", env=ENV
        )
        if result.returncode == 0:
            ok.append(f.name)
            print(f"  ✓ {f.name}")
        else:
            failed.append(f.name)
            print(f"  ✗ {f.name}")
            # last non-empty line of stderr = quick reason, full trace hidden
            err_lines = [l for l in result.stderr.strip().splitlines() if l.strip()]
            if err_lines:
                print(f"      {err_lines[-1]}")

    print(f"\n{len(ok)}/{len(files)} processed successfully")
    if failed:
        print(f"Failed: {', '.join(failed)}")

    print(f"\n{'='*40}\nEVAL RESULTS\n{'='*40}")
    subprocess.run([sys.executable, "eval.py", "invoice"], env=ENV)


if __name__ == "__main__":
    main()