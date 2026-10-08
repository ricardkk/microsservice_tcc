#!/usr/bin/env python3
"""Compare application sources and experiment implementation across both stacks."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SHARED_FILES = ("pom.xml", "Dockerfile", "mvnw", "mvnw.cmd", ".mvn/wrapper/maven-wrapper.properties",
                "scripts/smoke.py", "experiments/runner.py", "experiments/test_runner.py")


def shared_paths(directory):
    paths = set(SHARED_FILES)
    paths.update(str(path.relative_to(directory)) for path in (directory / "src").rglob("*") if path.is_file())
    paths.update(str(path.relative_to(directory)) for path in (directory / "experiments/scenarios").glob("*.sh"))
    return paths


def main():
    baseline, centralized = ROOT / "non_centralized", ROOT / "centralized"
    mismatches = []
    paths = shared_paths(baseline) | shared_paths(centralized)
    for name in sorted(paths):
        first, second = baseline / name, centralized / name
        if not first.exists() or not second.exists() or first.read_bytes() != second.read_bytes():
            mismatches.append(name)
    if mismatches:
        print("Divergência na aplicação/experimentos:\n" + "\n".join(mismatches), file=sys.stderr)
        return 1
    print(f"Paridade confirmada: {len(paths)} arquivos de aplicação/build/experimentos idênticos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
