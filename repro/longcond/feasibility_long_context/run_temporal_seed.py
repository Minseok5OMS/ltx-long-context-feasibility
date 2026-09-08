"""Run the four conditions of one seed, each in a fresh GPU process."""

import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=[43, 44], required=True)
    parser.add_argument("--gpu", type=int, choices=[0, 1, 2], required=True)
    args = parser.parse_args()
    script = Path(__file__).with_name("run_temporal_position.py")
    for kind in ("image", "video"):
        for position in ("past", "target"):
            subprocess.run([sys.executable, str(script), "--seed", str(args.seed), "--gpu", str(args.gpu),
                            "--reference-kind", kind, "--position", position], check=True)


if __name__ == "__main__":
    main()
