import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set

DATA_DIR = Path(__file__).parent / ".." / "data"

# Load data
with open(DATA_DIR / "tree.json") as f:
    tree_nodes = json.load(f)

with open(DATA_DIR / "annotations.json") as f:
    annotations = json.load(f)

with open(DATA_DIR / "relatives_10.json") as f:
    relatives = json.load(f)

# Helper maps
tree_by_id: Dict[str, dict] = {node["id"]: node for node in tree_nodes}
anno_by_id: Dict[str, dict] = {v["tree_node_id"]: v for v in annotations}
profile_id_to_tree_id: Dict[str, str] = {
    v["profile_id"]: k for k, v in tree_by_id.items() if v.get("profile_id")
}

# ID generators
gedcom_ids = {}
def get_gedcom_id(tree_id: str) -> str:
    if tree_id not in gedcom_ids:
        gedcom_ids[tree_id] = f"@I{len(gedcom_ids) + 1}@"
    return gedcom_ids[tree_id]

family_ids = []
def new_family_id() -> str:
    fid = f"@F{len(family_ids) + 1}@"
    family_ids.append(fid)
    return fid

def format_date(birth: dict) -> Optional[str]:
    if not birth or not birth.get("year"):
        return None
    try:
        parts = [str(birth.get("day", "")).zfill(2), str(birth.get("month", "")).zfill(2), str(birth.get("year"))]
        dt = datetime.strptime("-".join(parts), "%d-%m-%Y")
        return dt.strftime("%d %b %Y").upper()
    except Exception:
        return str(birth.get("year"))

def build_individual_entry(node_id: str, node: dict, annotation: Optional[dict]) -> List[str]:
    lines = [f"0 {get_gedcom_id(node_id)} INDI"]
    fname = (annotation.get("first_name") if annotation else None) or node.get("first_name")
    lname = (annotation.get("last_name") if annotation else None) or node.get("last_name")
    sex = (annotation.get("sex") if annotation else None) or node.get("sex")
    if fname or lname:
        lines.append(f"1 NAME {fname or ''} /{lname or ''}/")
    if sex:
        lines.append(f"1 SEX {sex[0].upper()}")
    if annotation and annotation.get("birth_occurrence"):
        bdate = format_date(annotation["birth_occurrence"])
        if bdate:
            lines.append("1 BIRT")
            lines.append(f"2 DATE {bdate}")
            loc = annotation["birth_occurrence"].get("city")
            if loc:
                lines.append(f"2 PLAC {loc}")
    if annotation and annotation.get("death_occurrence"):
        ddate = format_date(annotation["death_occurrence"])
        if ddate:
            lines.append("1 DEAT")
            lines.append(f"2 DATE {ddate}")
    return lines

def build_family_entries(tree_nodes: Dict[str, dict]) -> List[str]:
    fam_lines = []
    seen: Set[Tuple[str, str]] = set()
    for node_id, node in tree_by_id.items():
        for partner_id in node.get("partner_ids", []):
            key = tuple(sorted((node_id, partner_id)))
            if key in seen:
                continue
            seen.add(key)
            children = [k for k, v in tree_by_id.items() if set(v.get("parent_ids", [])) == set([node_id, partner_id])]
            node_sex = (tree_by_id.get(node_id) or {}).get("sex", "")
            node_sex = node_sex.upper() if node_sex else ""
            partner_sex = (tree_by_id.get(partner_id) or {}).get("sex", "")
            partner_sex = partner_sex.upper() if partner_sex else ""
            if node_sex == "M":
                fam_lines.append(f"1 HUSB {get_gedcom_id(node_id)}")
                fam_lines.append(f"1 WIFE {get_gedcom_id(partner_id)}")
            elif partner_sex == "M":
                fam_lines.append(f"1 HUSB {get_gedcom_id(partner_id)}")
                fam_lines.append(f"1 WIFE {get_gedcom_id(node_id)}")
            else:
                fam_lines.append(f"1 HUSB {get_gedcom_id(node_id)}")
                fam_lines.append(f"1 WIFE {get_gedcom_id(partner_id)}")
            for child in children:
                fam_lines.append(f"1 CHIL {get_gedcom_id(child)}")

    # Also add family entries based solely on parent_ids (e.g. for "you")
    seen_parents: Set[Tuple[str, str]] = set()
    for node_id, node in tree_by_id.items():
        parent_ids = node.get("parent_ids", [])
        if len(parent_ids) != 2:
            continue
        key = tuple(sorted(parent_ids))
        if key in seen_parents:
            continue
        seen_parents.add(key)
        children = [k for k, v in tree_by_id.items() if set(v.get("parent_ids", [])) == set(parent_ids)]
        fid = new_family_id()
        fam_lines.append(f"0 {fid} FAM")
        fam_lines.append(f"1 HUSB {get_gedcom_id(parent_ids[0])}")
        fam_lines.append(f"1 WIFE {get_gedcom_id(parent_ids[1])}")
        for child in children:
            fam_lines.append(f"1 CHIL {get_gedcom_id(child)}")
    return fam_lines


def export_gedcom(output_path: Path):
    lines: List[str] = ["0 HEAD"]

    # Individuals
    for node_id, node in tree_by_id.items():
        anno = anno_by_id.get(node_id)
        lines += build_individual_entry(node_id, node, anno)

    # Families
    lines += build_family_entries(tree_by_id)

    lines.append("0 TRLR")
    output_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    out_path = Path(__file__).parent / ".." / "output" / "export.ged"
    out_path.parent.mkdir(exist_ok=True)
    export_gedcom(out_path)
    print(f"[✓] GEDCOM export complete: {out_path.resolve()}")