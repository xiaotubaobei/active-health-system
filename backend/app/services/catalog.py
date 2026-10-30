import json
from pathlib import Path
from ..config import DATA_DIR


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_fitness_scales() -> list[dict]:
    root = DATA_DIR / "fitness_scales"
    return [_load(p) for p in sorted(root.glob("*.json"))]


def load_prescription_libs() -> dict:
    root = DATA_DIR / "prescription_templates"
    fitness = _load(root / "fitness.json")
    medical = _load(root / "medical.json")
    return {"fitness": fitness, "medical": medical}


def resolve_exercises(lib: dict, exercise_ids: list[str]) -> list[dict]:
    by_id = {e["id"]: e for e in lib.get("exercises", [])}
    out = []
    for eid in exercise_ids:
        if eid in by_id:
            e = dict(by_id[eid])
            e["sets"] = e.get("default_sets", 3)
            e["reps"] = e.get("default_reps", 10)
            out.append(e)
    return out
