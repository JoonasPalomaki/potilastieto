"""Utility to parse patient_system_requirements.csv into structured formats."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - handled in README instructions
    raise SystemExit(
        "PyYAML is required. Install dependencies before running this script"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
CSV_PATH = SPECS_DIR / "patient_system_requirements.csv"
STATUS_OVERRIDE_PATH = SPECS_DIR / "requirement_status.yml"
DEFAULT_OUTPUT = SPECS_DIR / "spec.json"


@dataclass
class RequirementNode:
    id: str
    parent: Optional[str]
    name: str
    klass: str
    lifecycle_status: str
    requirement_type: str
    description: str
    delivery_status: str = "todo"
    children: List["RequirementNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "parent": self.parent,
            "name": self.name,
            "class": self.klass,
            "lifecycle_status": self.lifecycle_status,
            "type": self.requirement_type,
            "description": self.description,
            "delivery_status": self.delivery_status,
            "children": [child.to_dict() for child in self.children],
        }


def load_status_overrides(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError("requirement_status.yml must be a mapping")
    normalized = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Status overrides must be string-to-string mappings")
        normalized[key.strip()] = value.strip()
    return normalized


def read_csv(path: Path) -> Iterable[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def build_tree(rows: Iterable[Dict[str, str]], overrides: Dict[str, str]) -> List[RequirementNode]:
    nodes: Dict[str, RequirementNode] = {}
    children_map: Dict[Optional[str], List[str]] = defaultdict(list)

    for row in rows:
        req_id = row["id"].strip()
        node = RequirementNode(
            id=req_id,
            parent=row["parent"].strip() or None,
            name=row["name"].strip(),
            klass=row["class"].strip(),
            lifecycle_status=row["status"].strip(),
            requirement_type=row.get("type", "").strip(),
            description=row.get("description", "").strip(),
            delivery_status=overrides.get(req_id, "todo"),
        )
        nodes[req_id] = node
        children_map[node.parent].append(req_id)

    for parent_id, child_ids in children_map.items():
        if parent_id is None:
            continue
        parent = nodes.get(parent_id)
        if parent is None:
            raise KeyError(f"Missing parent '{parent_id}' for child nodes {child_ids}")
        parent.children.extend(nodes[child_id] for child_id in child_ids)

    root_ids = children_map[None]
    return [nodes[root_id] for root_id in root_ids]


def serialize(nodes: List[RequirementNode], output_format: str) -> str:
    payload = [node.to_dict() for node in nodes]
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if output_format == "yaml":
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    raise ValueError(f"Unsupported format: {output_format}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render requirement specification into JSON/YAML")
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    overrides = load_status_overrides(STATUS_OVERRIDE_PATH)
    rows = list(read_csv(CSV_PATH))
    nodes = build_tree(rows, overrides)
    rendered = serialize(nodes, args.format)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")

    print(f"Wrote {args.output} in {args.format.upper()} format with {len(rows)} entries.")


if __name__ == "__main__":
    main()
