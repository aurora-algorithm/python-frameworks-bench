"""Shares of time per function in py-spy's speedscope profiles: for each function, the share of samples it was on
the stack (inclusive) or at the top (self). Writes profiles/analysis.json for make_script.py.

usage: python3 analyze_profile.py profiles/*.speedscope.json
"""

import json
import sys
from collections import Counter
from pathlib import Path


def label(frame: dict) -> str:
    """function [package or module], the way the video names it: jsonable_encoder [fastapi]."""
    path = frame.get("file", "")
    package = path.split("site-packages/")[-1].split("/")[0] if "site-packages/" in path else Path(path).stem
    return f"{frame['name']} [{package}]"


def analyze(path: Path) -> dict:
    data = json.loads(path.read_text())
    frames = [label(f) for f in data["shared"]["frames"]]
    inclusive, top = Counter(), Counter()
    total = 0
    for profile in data["profiles"]:
        for stack, weight in zip(profile["samples"], profile["weights"], strict=True):
            # py-spy samples idle threads too; count only stacks that were running Python code.
            if not stack:
                continue
            total += weight
            for name in {frames[i] for i in stack}:
                inclusive[name] += weight
            top[frames[stack[-1]]] += weight
    return {
        "samples": total,
        "inclusive": {k: v / total for k, v in inclusive.most_common(60)},
        "self": {k: v / total for k, v in top.most_common(30)},
    }


def main() -> None:
    out = {Path(p).name.removesuffix(".speedscope.json"): analyze(Path(p)) for p in sys.argv[1:]}
    target = Path(sys.argv[1]).parent / "analysis.json"
    target.write_text(json.dumps(out, indent=1) + "\n")
    for name, result in out.items():
        print(name, result["samples"], "samples")
        for fn, share in list(result["inclusive"].items())[:12]:
            print(f"  {share:6.1%}  {fn}")


if __name__ == "__main__":
    main()
