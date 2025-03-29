import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set

DATA_DIR = Path(__file__).parent / ".." / "data"

class GedcomIdGenerator:
    def __init__(self):
        self.gedcom_ids = {}
        self.family_ids = []
        self.family_structs: List[Tuple[str, str, str, List[str]]] = []

    def get_gedcom_id(self, key: str) -> str:
        if key not in self.gedcom_ids:
            self.gedcom_ids[key] = f"@I{len(self.gedcom_ids) + 1}@"
        return self.gedcom_ids[key]

    def new_family_id(self) -> str:
        fid = f"@F{len(self.family_ids) + 1}@"
        self.family_ids.append(fid)
        return fid

gedcom = GedcomIdGenerator()

def load_data(data_dir: Path) -> Tuple[List[dict], List[dict], List[dict]]:
    with open(data_dir / "tree.json") as f:
        tree_nodes = json.load(f)
    with open(data_dir / "annotations.json") as f:
        annotations = json.load(f)
    with open(data_dir / "relatives_10.json") as f:
        relatives = json.load(f)
    return tree_nodes, annotations, relatives

def normalize_tree_nodes(tree_nodes: List[dict]) -> Dict[str, dict]:
    id_to_profile = {}
    profile_to_id = {}
    for node in tree_nodes:
        pid = node.get("profile_id")
        nid = node.get("id")
        if pid:
            profile_to_id[pid] = nid
            id_to_profile[nid] = pid

    tree_by_id: Dict[str, dict] = {}
    for node in tree_nodes:
        key = node.get("profile_id") or node["id"]
        if not key:
            continue
        normalized_node = dict(node)  # shallow copy
        normalized_node["id"] = key

        normalized_node["parent_ids"] = [
            id_to_profile.get(pid, pid) for pid in node.get("parent_ids", [])
        ]
        normalized_node["partner_ids"] = [
            id_to_profile.get(pid, pid) for pid in node.get("partner_ids", [])
        ]
        tree_by_id[key] = normalized_node
    return tree_by_id

def map_annotations(annotations: List[dict]) -> Dict[str, dict]:
    anno_by_id: Dict[str, dict] = {}
    for v in annotations:
        key = v.get("profile_id") or v["tree_node_id"]
        if key:
            anno_by_id[key] = v
    return anno_by_id

# Load data
tree_nodes, annotations, relatives = load_data(DATA_DIR)

# First pass: build ID maps
id_to_profile = {}
profile_to_id = {}
for node in tree_nodes:
    pid = node.get("profile_id")
    nid = node.get("id")
    if pid:
        profile_to_id[pid] = nid
        id_to_profile[nid] = pid

# Second pass: normalize IDs
tree_by_id = normalize_tree_nodes(tree_nodes)

anno_by_id = map_annotations(annotations)

profile_id_to_tree_id: Dict[str, str] = {
    v["profile_id"]: k for k, v in tree_by_id.items() if v.get("profile_id")
}

seen_gedcom_ids: Set[str] = set()
def format_date(birth: dict) -> Optional[str]:
    if not birth or not birth.get("year"):
        return None
    try:
        parts = [str(birth.get("day", "")).zfill(2), str(birth.get("month", "")).zfill(2), str(birth.get("year"))]
        dt = datetime.strptime("-".join(parts), "%d-%m-%Y")
        return dt.strftime("%d %b %Y").upper()
    except Exception:
        return str(birth.get("year"))

def format_place(loc_dict):
    if not loc_dict:
        return None
    return ", ".join(
        filter(None, [loc_dict.get("city"), loc_dict.get("state"), loc_dict.get("county"), loc_dict.get("country")])
    )

def build_individual_entry(node_id: str, node: dict, annotation: Optional[dict]) -> List[str]:
    lines = [f"0 {gedcom.get_gedcom_id(node_id)} INDI"]
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
            plac = format_place(annotation["birth_occurrence"])
            if plac:
                lines.append(f"2 PLAC {plac}")
    if annotation and annotation.get("death_occurrence"):
        ddate = format_date(annotation["death_occurrence"])
        if ddate:
            lines.append("1 DEAT")
            lines.append(f"2 DATE {ddate}")
            plac = format_place(annotation["death_occurrence"])
            if plac:
                lines.append(f"2 PLAC {plac}")

    if annotation and annotation.get("residence_occurrence"):
        plac = format_place(annotation["residence_occurrence"])
        if plac:
            lines.append("1 RESI")
            lines.append(f"2 PLAC {plac}")

    if node.get("profile_image_url"):
        lines.append("1 OBJE")
        lines.append(f"2 FILE {node['profile_image_url']}")

    for fam_id, husb_id, wife_id, children in gedcom.family_structs:
        if node_id in children:
            lines.append(f"1 FAMC {fam_id}")
        elif node_id == husb_id or node_id == wife_id:
            lines.append(f"1 FAMS {fam_id}")

    if gedcom.get_gedcom_id(node_id) in seen_gedcom_ids:
        return []
    seen_gedcom_ids.add(gedcom.get_gedcom_id(node_id))

    return lines

def build_partner_families(tree_nodes: Dict[str, dict]) -> List[str]:
    fam_lines = []
    seen: Set[Tuple[str, str]] = set()
    for node_id, node in tree_nodes.items():
        for partner_id in node.get("partner_ids", []):
            key = tuple(sorted((node_id, partner_id)))
            if key in seen:
                continue
            seen.add(key)
            children = [
                k for k, v in tree_nodes.items()
                if set([node_id, partner_id]).issubset(set(v.get("parent_ids", [])))
            ]
            node_sex = node.get("sex", "")
            node_sex = node_sex.upper() if node_sex else ""
            partner_node = tree_nodes.get(partner_id)
            partner_sex = ""
            if partner_node and partner_node.get("sex"):
                partner_sex = partner_node["sex"].upper()
            fid = gedcom.new_family_id()
            fam_lines.append(f"0 {fid} FAM")
            if node_sex == "M":
                fam_lines.append(f"1 HUSB {gedcom.get_gedcom_id(node_id)}")
                fam_lines.append(f"1 WIFE {gedcom.get_gedcom_id(partner_id)}")
            elif node_sex == "F":
                fam_lines.append(f"1 WIFE {gedcom.get_gedcom_id(node_id)}")
                fam_lines.append(f"1 HUSB {gedcom.get_gedcom_id(partner_id)}")
            else:
                fam_lines.append(f"1 HUSB {gedcom.get_gedcom_id(node_id)}")
                fam_lines.append(f"1 WIFE {gedcom.get_gedcom_id(partner_id)}")
            for child in children:
                fam_lines.append(f"1 CHIL {gedcom.get_gedcom_id(child)}")
            gedcom.family_structs.append((fid, node_id, partner_id, children))
    return fam_lines

def build_parent_based_families(tree_nodes: Dict[str, dict]) -> List[str]:
    fam_lines = []
    seen_families: Set[Tuple[str, str]] = set()
    for node_id, node in tree_nodes.items():
        parent_ids = node.get("parent_ids", [])
        if len(parent_ids) != 2:
            continue
        pid1, pid2 = sorted(parent_ids)
        family_key = (pid1, pid2)
        if family_key in seen_families:
            continue
        seen_families.add(family_key)
        fid = gedcom.new_family_id()
        fam_lines.append(f"0 {fid} FAM")
        fam_lines.append(f"1 HUSB {gedcom.get_gedcom_id(pid1)}")
        fam_lines.append(f"1 WIFE {gedcom.get_gedcom_id(pid2)}")
        children = [
            cid for cid, cnode in tree_nodes.items()
            if set(cnode.get("parent_ids", [])) == set(family_key)
        ]
        for cid in children:
            fam_lines.append(f"1 CHIL {gedcom.get_gedcom_id(cid)}")
        gedcom.family_structs.append((fid, pid1, pid2, children))
    return fam_lines

def build_family_entries(tree_nodes: Dict[str, dict]) -> List[str]:
    return build_partner_families(tree_nodes) + build_parent_based_families(tree_nodes)

def export_gedcom(output_path: Path):
    lines: List[str] = [
        "0 HEAD",
        "1 SOUR 23andMeScraper",
        "2 VERS 1.0",
        "2 NAME 23andMe Family Tree Exporter",
        "1 CHAR UTF-8",
        "1 GEDC",
        "2 VERS 5.5.1",
        "2 FORM LINEAGE-LINKED"
    ]

    lines += build_family_entries(tree_by_id)

    for node_id, node in tree_by_id.items():
        anno = anno_by_id.get(node_id)
        lines += build_individual_entry(node_id, node, anno)

    lines.append("0 TRLR")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(gedcom.gedcom_ids)} individuals and {len(gedcom.family_ids)} families.")

if __name__ == "__main__":
    out_path = Path(__file__).parent / ".." / "output" / "export.ged"
    out_path.parent.mkdir(exist_ok=True)
    export_gedcom(out_path)
    print(f"[✓] GEDCOM export complete: {out_path.resolve()}")