from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from nodetrade.training import ModelGate, ModelRegistry, evaluate_candidate, validate_dataset, walk_forward_evaluate


def run(dataset: str, registry: str = "models") -> dict:
    path = Path(dataset)
    if not path.exists():
        return {"status": "pending", "reason": "training dataset not available", "production_changed": False}
    frame = pd.read_csv(path)
    validate_dataset(frame)
    result = evaluate_candidate(frame)
    version = "candidate-" + hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    registry_obj = ModelRegistry(registry)
    metadata = {
        "version": version,
        "dataset": str(path),
        "samples": result.samples,
        "evaluation": {"status": result.status, "metrics": result.metrics, "reason": result.reason},
        "walk_forward": {"rows": int(len(walk_forward_evaluate(frame)))},
        "approved": ModelGate().approve(result),
        "production_changed": False,
    }
    registry_obj.register(version, metadata)
    # Explicitly never promote here. Production promotion is a separate, audited operation.
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/training.csv")
    parser.add_argument("--registry", default="models")
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.registry), indent=2, sort_keys=True))
