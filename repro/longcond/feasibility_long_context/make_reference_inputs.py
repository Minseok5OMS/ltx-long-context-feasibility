"""Export actual pre-VAE RGB previews and input provenance for completed diagnostics."""

import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from run_generation import ROOT, read_rgb, sha256, write_json


def build_input_previews():
    examples = {}
    summaries = sorted((ROOT / "reports/reference").glob("*/*/summary.json"))
    for summary_path in summaries:
        summary = json.loads(summary_path.read_text())
        name = summary["example_id"]
        if name in examples:
            continue
        group = ROOT / "outputs" / name / f'reference_{summary["layout"]}_seed{summary["seed"]}'
        configs = {m: json.loads((group / m / "config.json").read_text()) for m in ["local", "random", "oracle"]}
        cfg = configs["local"]
        data = ROOT / "data" / name
        metadata = json.loads((data / "metadata.json").read_text())
        cache = ROOT / "outputs" / name / f'reference_inputs_{cfg["width"]}x{cfg["height"]}'
        inputs = json.loads((cache / "inputs.json").read_text())
        if inputs["fingerprint"]["metadata_sha256"] != sha256(data / "metadata.json"):
            raise ValueError("Metadata differs from generation input preparation")
        if any(c["common_inputs_sha256"] != inputs["inputs_sha256"] for c in configs.values()):
            raise ValueError("Input cache does not match completed conditions")
        if sha256(cache / "inputs.pt") != inputs["inputs_sha256"]:
            raise ValueError("Input cache changed")
        output = ROOT / "reports/reference/inputs" / name
        output.mkdir(parents=True, exist_ok=True)
        width, height = cfg["width"], cfg["height"]
        sheet = Image.new("RGB", (width * 4, (height + 44) * 3), "#141923")
        draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=18)
        clips = {}
        for column, kind in enumerate(["local", "random", "oracle", "target"]):
            info = metadata["clips"][kind]
            source = data / info["file"]
            if sha256(source) != info["sha256"]:
                raise ValueError(f"Changed clip: {source}")
            rgb = read_rgb(source, width, height)
            assert len(rgb) == info["frames"]
            indices = [0, len(rgb) // 2, len(rgb) - 1]
            mid = indices[1]
            middle = output / f"{kind}_middle.png"
            Image.fromarray(rgb[mid]).save(middle)
            assert np.array_equal(np.asarray(Image.open(middle)), rgb[mid])
            for row, index in enumerate(indices):
                y = row * (height + 44)
                sheet.paste(Image.fromarray(rgb[index]), (column * width, y + 44))
                label = "GT (evaluation only)" if kind == "target" else kind.capitalize()
                draw.text((column * width + 8, y + 3), f"{label} | clip frame {index}", font=font, fill="white")
                draw.text((column * width + 8, y + 23), f"source {info['source_frame_seconds'][index]:.6f}s", font=font, fill="white")
            clips[kind] = {"file": str(source.relative_to(ROOT)), "sha256": info["sha256"],
                           "requested_source_range": [metadata[kind + "_start"], metadata[kind + "_end"]],
                           "frames": len(rgb), "preview_frame_indices": indices,
                           "middle_frame_index": mid, "middle_clip_pts_seconds": mid / metadata["clip_fps"],
                           "middle_source_pts_seconds": info["source_frame_seconds"][mid],
                           "middle_png": str(middle.relative_to(ROOT)), "middle_png_sha256": sha256(middle),
                           "middle_rgb_sha256": hashlib.sha256(rgb[mid].tobytes()).hexdigest()}
        sheet_path = output / "inputs_overview.jpg"
        sheet.save(sheet_path, quality=94)
        result = {"example_id": name, "source_provenance": metadata["source_provenance"],
                  "metadata_sha256": sha256(data / "metadata.json"), "common_inputs_sha256": inputs["inputs_sha256"],
                  "preprocessing": "Same read_rgb as generation: centered Lanczos crop/resize to 512x288, before BF16 normalization and VAE",
                  "images": "Middle PNGs are lossless pre-VAE RGB; overview JPEG is a three-frame visual summary",
                  "gt_role": "Evaluation-only preview; never a generation input",
                  "prompt": metadata["prompt"], "cached_shapes": inputs["shapes"], "clips": clips,
                  "overview": str(sheet_path.relative_to(ROOT))}
        write_json(output / "inputs.json", result)
        examples[name] = result
    return examples


if __name__ == "__main__":
    for name, result in build_input_previews().items():
        print(name, result["overview"])
