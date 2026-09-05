from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from nodetrade.model import CausalDirectionModel
from nodetrade.training import ModelGate, ModelRegistry, evaluate_candidate, validate_dataset, walk_forward_evaluate


def run(dataset: str, registry: str = "models") -> dict:
    path = Path(dataset)
    registry_obj = ModelRegistry(registry)
    if not path.exists():
        return {"status": "pending", "reason": "training dataset not available", "production_changed": False}

    frame = pd.read_csv(path)
    validate_dataset(frame)
    result = evaluate_candidate(frame)
    version = "candidate-" + hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    artifact = Path(registry) / f"{version}.pkl"

    metadata = {
        "version": version,
        "dataset": str(path),
        "samples": result.samples,
        "evaluation": {"status": result.status, "metrics": result.metrics, "reason": result.reason},
        "walk_forward": {"rows": int(len(walk_forward_evaluate(frame)))},
        "approved": ModelGate().approve(result),
        "artifact": str(artifact),
        "production_changed": False,
    }

    # Train and persist only a candidate artifact. This worker never promotes production.
    if result.status == "passed":
        candidate = CausalDirectionModel(horizon=5).fit(frame)
        if candidate.fitted:
            candidate.save(artifact)
        else:
            metadata["approved"] = False
            metadata["evaluation"]["reason"] = "candidate model could not fit"
            metadata["evaluation"]["status"] = "failed"

    registry_obj.register(version, metadata)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/training.csv")
    parser.add_argument("--registry", default="models")
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.registry), indent=2, sort_keys=True))
