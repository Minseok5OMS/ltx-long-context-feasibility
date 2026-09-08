"""Run one fresh model process at a time on each authorized GPU (0, 1, 2)."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from run_generation import ROOT, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["prepare", "generate"], required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "configs/five_case_examples.json").read_text())
    directory = ROOT / "outputs/five_case_batch"
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = directory / "source_snapshot"
    snapshot.mkdir(exist_ok=True)
    for name in ("run_five_case_batch.py", "run_five_case_comparison.py", "prepare_five_cases.py",
                 "reference_controls.py", "run_generation.py", "decode_five_case_latent.py"):
        source, destination = ROOT / name, snapshot / name
        if destination.exists() and sha256(destination) != sha256(source):
            raise ValueError(f"Code changed after batch freeze: {name}")
        shutil.copyfile(source, destination)
    protocol = ROOT / "configs/five_case_examples.json"
    frozen = snapshot / protocol.name
    if frozen.exists() and sha256(frozen) != sha256(protocol):
        raise ValueError("Cohort changed after freeze")
    shutil.copyfile(protocol, frozen)

    def worker(gpu):
        records = []
        for example in config["examples"][gpu::3]:
            modes = ["prepare"] if args.phase == "prepare" else ["local", "oracle"]
            for mode in modes:
                command = [sys.executable, str(ROOT / "run_five_case_comparison.py"), "--example",
                           str(ROOT / "data" / example["example_id"]), "--gpu", str(gpu)]
                command += ["--prepare-inputs"] if mode == "prepare" else ["--mode", mode]
                log = directory / f'{example["example_id"]}_{mode}.log'
                record = {"example_id": example["example_id"], "mode": mode, "physical_gpu": gpu,
                          "command": shlex.join(command), "log": str(log),
                          "started_at_utc": datetime.now(timezone.utc).isoformat()}
                print(f'Start GPU {gpu}: {example["example_id"]}/{mode}', flush=True)
                with log.open("a", encoding="utf-8") as stream:
                    result = subprocess.run(command, cwd=ROOT.parent, stdout=stream, stderr=subprocess.STDOUT)
                record.update(returncode=result.returncode, finished_at_utc=datetime.now(timezone.utc).isoformat())
                records.append(record)
                write_json(directory / f"{args.phase}_gpu{gpu}.json", records)
                if result.returncode:
                    raise RuntimeError(f"Failed: {command}; see {log}")
                print(f'Complete GPU {gpu}: {example["example_id"]}/{mode}', flush=True)
        return records

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(worker, gpu) for gpu in (0, 1, 2)]
        records = [record for future in futures for record in future.result()]
    write_json(directory / f"{args.phase}_ledger.json", {"records": records, "status": "completed",
               "cohort_config_sha256": sha256(protocol), "batch_script_sha256": sha256(Path(__file__))})


if __name__ == "__main__":
    main()
