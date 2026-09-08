"""Exact repetitions of the independently encoded past image; no RGB re-encoding."""

from format_controls import EXAMPLE, ReferenceTimeLayout, case_path as format_case_path
from run_generation import ROOT


CASES = {f"N{n}": {"name": f"repeat_{n}", "key": "oracle_still", "repeats": n,
                    "layout": "same", "tokens": 144 * n} for n in (1, 2, 4, 10)}


def case_path(case, seed=42):
    if seed != 42 or case not in CASES:
        raise ValueError("This diagnostic uses N1/N2/N4/N10 at seed 42")
    if case in ("N1", "N10"):
        return format_case_path("A" if case == "N1" else "B", seed)
    return ROOT / "outputs" / EXAMPLE / f"reference_repetition_seed{seed}" / CASES[case]["name"]


def reference_tensor(tensors, case):
    source = tensors["oracle_still"]
    if tuple(source.shape) != (1, 128, 1, 9, 16):
        raise ValueError("Expected the original independently encoded image")
    return source.repeat(1, 1, CASES[case]["repeats"], 1, 1)
