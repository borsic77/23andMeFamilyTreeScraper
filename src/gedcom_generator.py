import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set

DATA_DIR = Path(__file__).parent / ".." / "data"

class GedcomIdGenerator:
    def __init__(self):
        """Initialize the GedcomIdGenerator with empty ID mappings."""
        self.gedcom_ids = {}
        self.family_ids = []
        self.family_structs: List[Tuple[str, str, str, List[str]]] = []

    def get_gedcom_id(self, key: str) -> str:
        """Get the GEDCOM ID for a given key, generating a new one if necessary.

        Args:
            key (str): The key for which to get the GEDCOM ID.

        Returns:
            str: The GEDCOM ID associated with the key.
        """
        if key not in self.gedcom_ids:
            self.gedcom_ids[key] = f"@I{len(self.gedcom_ids) + 1}@"
        return self.gedcom_ids[key]

    def new_family_id(self) -> str:
        """Generate a new family ID.

        Returns:
            str: A new family ID.
        """
        fid = f"@F{len(self.family_ids) + 1}@"
        self.family_ids.append(fid)
        return fid

def load_data(data_dir: Path) -> Tuple[List[dict], List[dict], List[dict]]:
    """Load data from JSON files in the specified directory.

    Args:
        data_dir (Path): The directory containing the JSON files.

    Returns:
        Tuple[List[dict], List[dict], List[dict]]: The loaded tree nodes, annotations, and relatives.
    """
    with open(data_dir / "tree.json") as f:
        tree_nodes = json.load(f)
    with open(data_dir / "annotations.json") as f:
        annotations = json.load(f)
    with open(data_dir / "relatives_10.json") as f:
        relatives = json.load(f)
    return tree_nodes, annotations, relatives

def normalize_tree_nodes(tree_nodes: List[dict]) -> Dict[str, dict]:
    """Normalize tree nodes to map profile IDs to node IDs.

    Args:
        tree_nodes (List[dict]): The list of tree nodes to normalize.

    Returns:
        Dict[str, dict]: A dictionary mapping normalized IDs to tree nodes.
    """
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
        key = node.get("profile_id") or node["id"]  # Use profile_id or id as key
        if not key:
            continue
        normalized_node = dict(node)  # shallow copy
        normalized_node["id"] = key

        # Normalize parent and partner IDs using the mapping
        normalized_node["parent_ids"] = [
            id_to_profile.get(pid, pid) for pid in node.get("parent_ids", [])
        ]
        normalized_node["partner_ids"] = [
            id_to_profile.get(pid, pid) for pid in node.get("partner_ids", [])
        ]
        tree_by_id[key] = normalized_node
    return tree_by_id

def map_annotations(annotations: List[dict]) -> Dict[str, dict]:
    """Map annotations to their corresponding profile or tree node IDs.

    Args:
        annotations (List[dict]): The list of annotations to map.

    Returns:
        Dict[str, dict]: A dictionary mapping IDs to their annotations.
    """
    anno_by_id: Dict[str, dict] = {}
    for v in annotations:
        key = v.get("profile_id") or v["tree_node_id"]
        if key:
            anno_by_id[key] = v
    return anno_by_id

class GedcomExporter:
    def __init__(self, tree_nodes: List[dict], annotations: List[dict], relatives: List[dict], verbose: bool = True):
        """Initialize the GedcomExporter with tree nodes, annotations, and relatives.

        Args:
            tree_nodes (List[dict]): The raw tree nodes.
            annotations (List[dict]): The annotations corresponding to the tree nodes.
            relatives (List[dict]): The relatives data.
            verbose (bool, optional): Flag for verbose output. Defaults to True.
        """
        self.tree_nodes_raw = tree_nodes
        self.annotations = annotations
        self.relatives = relatives
        self.verbose = verbose

        self.tree_by_id = normalize_tree_nodes(tree_nodes)
        self.anno_by_id = map_annotations(annotations)
        # Map profile IDs to tree node IDs for easy access
        self.profile_id_to_tree_id = {
            v["profile_id"]: k for k, v in self.tree_by_id.items() if v.get("profile_id")
        }

        self.gedcom = GedcomIdGenerator()
        self.seen_gedcom_ids: Set[str] = set()
        self.created_families: Set[Tuple[str, str]] = set()

    def generate_gedcom_lines(self) -> List[str]:
        """Generate GEDCOM lines for the export.

        Returns:
            List[str]: The list of GEDCOM lines.
        """
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

        lines += self.build_family_entries()  # Add family entries

        for node_id, node in self.tree_by_id.items():
            anno = self.anno_by_id.get(node_id)
            lines += self.build_individual_entry(node_id, node, anno)

        lines.append("0 TRLR")
        return lines

    def write_to_file(self, lines: List[str], output_path: Path):
        """Write the generated GEDCOM lines to a file.

        Args:
            lines (List[str]): The list of GEDCOM lines to write.
            output_path (Path): The path to the output file.
        """
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def export(self, output_path: Path):
        """Export the GEDCOM data to a file.

        Args:
            output_path (Path): The path to the output GEDCOM file.
        """
        lines = self.generate_gedcom_lines()
        self.write_to_file(lines, output_path)
        if self.verbose:
            print(f"Exported {len(self.gedcom.gedcom_ids)} individuals and {len(self.gedcom.family_ids)} families.")

    def _format_name(self, fname: Optional[str], lname: Optional[str]) -> Optional[str]:
        """Format the name for GEDCOM output.

        Args:
            fname (Optional[str]): The first name.
            lname (Optional[str]): The last name.

        Returns:
            Optional[str]: Formatted name string for GEDCOM.
        """
        if fname or lname:
            return f"1 NAME {fname} /{lname}/"
        return None

    def _format_sex(self, sex: Optional[str]) -> Optional[str]:
        """Format the sex for GEDCOM output.

        Args:
            sex (Optional[str]): The sex of the individual.

        Returns:
            Optional[str]: Formatted sex string for GEDCOM.
        """
        if sex:
            return f"1 SEX {sex}"
        return None

    def _format_birth(self, annotation: dict) -> List[str]:
        """Format birth information for GEDCOM output.

        Args:
            annotation (dict): The annotation containing birth information.

        Returns:
            List[str]: List of GEDCOM lines for birth information.
        """
        lines = []
        occ = annotation.get("birth_occurrence")
        if occ:
            date_str = self.format_date_from_fields(occ)
            place_str = self.format_place_from_fields(occ)
            if date_str or place_str:
                lines.append("1 BIRT")
                if date_str:
                    lines.append(f"2 DATE {date_str}")
                if place_str:
                    lines.append(f"2 PLAC {place_str}")
        return lines

    def _format_death(self, annotation: dict) -> List[str]:
        """Format death information for GEDCOM output.

        Args:
            annotation (dict): The annotation containing death information.

        Returns:
            List[str]: List of GEDCOM lines for death information.
        """
        lines = []
        occ = annotation.get("death_occurrence")
        if occ:
            date_str = self.format_date_from_fields(occ)
            place_str = self.format_place_from_fields(occ)
            if date_str or place_str:
                lines.append("1 DEAT")
                if date_str:
                    lines.append(f"2 DATE {date_str}")
                if place_str:
                    lines.append(f"2 PLAC {place_str}")
        return lines

    def _format_residence(self, annotation: dict) -> List[str]:
        """Format residence information for GEDCOM output.

        Args:
            annotation (dict): The annotation containing residence information.

        Returns:
            List[str]: List of GEDCOM lines for residence information.
        """
        lines = []
        occ = annotation.get("residence_occurrence")
        if occ:
            date_str = self.format_date_from_fields(occ)
            place_str = self.format_place_from_fields(occ)
            if date_str or place_str:
                lines.append("1 RESI")
                if date_str:
                    lines.append(f"2 DATE {date_str}")
                if place_str:
                    lines.append(f"2 PLAC {place_str}")
        return lines

    def _format_image(self, node: dict) -> List[str]:
        """Format image information for GEDCOM output.

        Args:
            node (dict): The node containing image information.

        Returns:
            List[str]: List of GEDCOM lines for image information.
        """
        lines = []
        if "image" in node:
            lines.append(f"1 OBJE {node['image']}")
        return lines

    def format_date(self, date_str: Optional[str]) -> Optional[str]:
        """Format a date string into GEDCOM format.

        Args:
            date_str (Optional[str]): The date string to format.

        Returns:
            Optional[str]: Formatted date string for GEDCOM.
        """
        if date_str:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %b %Y")
        return None

    def format_place(self, place_str: Optional[str]) -> Optional[str]:
        """Return the place string for GEDCOM output.

        Args:
            place_str (Optional[str]): The place string to format.

        Returns:
            Optional[str]: The place string for GEDCOM.
        """
        return place_str if place_str else None

    def format_date_from_fields(self, occ: dict) -> Optional[str]:
        """Format date from 'day', 'month', and 'year' fields in annotation."""
        day = occ.get("day")
        month = occ.get("month")
        year = occ.get("year")
        if year:
            try:
                return datetime(year, month or 1, day or 1).strftime("%d %b %Y") if month and day else \
                       datetime(year, month or 1, 1).strftime("%b %Y") if month else \
                       f"{year}"
            except Exception:
                return None
        return None

    def format_place_from_fields(self, occ: dict) -> Optional[str]:
        """Format place from structured location fields in annotation."""
        parts = [occ.get("city"), occ.get("county"), occ.get("state"), occ.get("country")]
        return ", ".join(p for p in parts if p)

    def build_individual_entry(self, node_id: str, node: dict, annotation: Optional[dict]) -> List[str]:
        """Build a GEDCOM entry for an individual.

        Args:
            node_id (str): The ID of the individual node.
            node (dict): The individual node data.
            annotation (Optional[dict]): The annotation for the individual.

        Returns:
            List[str]: List of GEDCOM lines for the individual.
        """
        lines = [f"0 {self.gedcom.get_gedcom_id(node_id)} INDI"]
        fname = (annotation.get("first_name") if annotation else None) or node.get("first_name")
        lname = (annotation.get("last_name") if annotation else None) or node.get("last_name")
        sex = (annotation.get("sex") if annotation else None) or node.get("sex")

        name_line = self._format_name(fname, lname)
        if name_line:
            lines.append(name_line)

        sex_line = self._format_sex(sex)
        if sex_line:
            lines.append(sex_line)

        if annotation:
            lines.extend(self._format_birth(annotation))
            lines.extend(self._format_death(annotation))
            lines.extend(self._format_residence(annotation))

        lines.extend(self._format_image(node))

        # Check for family relationships and add them to the lines
        for fam_id, husb_id, wife_id, children in self.gedcom.family_structs:
            if node_id in children:
                lines.append(f"1 FAMC {fam_id}")  # Child entry
            elif node_id == husb_id or node_id == wife_id:
                lines.append(f"1 FAMS {fam_id}")  # Parent entry

        # Ensure we don't duplicate entries for the same individual
        if self.gedcom.get_gedcom_id(node_id) in self.seen_gedcom_ids:
            return []
        self.seen_gedcom_ids.add(self.gedcom.get_gedcom_id(node_id))

        return lines

    def build_partner_families(self) -> List[str]:
        """Build GEDCOM entries for families based on partner relationships.

        Returns:
            List[str]: List of GEDCOM lines for partner families.
        """
        fam_lines = []
        for node_id, node in self.tree_by_id.items():
            for partner_id in node.get("partner_ids", []):
                family_key = tuple(sorted((node_id, partner_id)))  # Create a unique family key
                if family_key in self.created_families:
                    continue
                self.created_families.add(family_key)
                children = [
                    k for k, v in self.tree_by_id.items()
                    if set([node_id, partner_id]).issubset(set(v.get("parent_ids", [])))  # Find children of the couple
                ]
                node_sex = node.get("sex", "")
                node_sex = node_sex.upper() if node_sex else ""
                partner_node = self.tree_by_id.get(partner_id)
                partner_sex = ""
                if partner_node and partner_node.get("sex"):
                    partner_sex = partner_node["sex"].upper()
                fid = self.gedcom.new_family_id()
                fam_lines.append(f"0 {fid} FAM")  # Start family entry
                if node_sex == "M":
                    fam_lines.append(f"1 HUSB {self.gedcom.get_gedcom_id(node_id)}")  # Husband
                    fam_lines.append(f"1 WIFE {self.gedcom.get_gedcom_id(partner_id)}")  # Wife
                elif node_sex == "F":
                    fam_lines.append(f"1 WIFE {self.gedcom.get_gedcom_id(node_id)}")  # Wife
                    fam_lines.append(f"1 HUSB {self.gedcom.get_gedcom_id(partner_id)}")  # Husband
                else:
                    fam_lines.append(f"1 HUSB {self.gedcom.get_gedcom_id(node_id)}")  # Default to Husband
                    fam_lines.append(f"1 WIFE {self.gedcom.get_gedcom_id(partner_id)}")  # Default to Wife
                for child in children:
                    fam_lines.append(f"1 CHIL {self.gedcom.get_gedcom_id(child)}")  # Add children
                self.gedcom.family_structs.append((fid, node_id, partner_id, children))  # Store family structure
        return fam_lines

    def build_parent_based_families(self) -> List[str]:
        """Build GEDCOM entries for families based on parent relationships.

        Returns:
            List[str]: List of GEDCOM lines for parent families.
        """
        fam_lines = []
        for node_id, node in self.tree_by_id.items():
            parent_ids = node.get("parent_ids", [])
            if len(parent_ids) != 2:  # Ensure there are exactly two parents
                continue
            pid1, pid2 = sorted(parent_ids)  # Sort parent IDs for consistency
            family_key = (pid1, pid2)
            if family_key in self.created_families:
                continue
            self.created_families.add(family_key)
            fid = self.gedcom.new_family_id()
            fam_lines.append(f"0 {fid} FAM")  # Start family entry
            fam_lines.append(f"1 HUSB {self.gedcom.get_gedcom_id(pid1)}")  # Husband
            fam_lines.append(f"1 WIFE {self.gedcom.get_gedcom_id(pid2)}")  # Wife
            children = [
                cid for cid, cnode in self.tree_by_id.items()
                if set(cnode.get("parent_ids", [])) == set(family_key)  # Find children of the parents
            ]
            for cid in children:
                fam_lines.append(f"1 CHIL {self.gedcom.get_gedcom_id(cid)}")  # Add children
            self.gedcom.family_structs.append((fid, pid1, pid2, children))  # Store family structure
        return fam_lines

    def build_family_entries(self) -> List[str]:
        """Build all family entries for the GEDCOM export.

        Returns:
            List[str]: Combined list of GEDCOM lines for all families.
        """
        return self.build_partner_families() + self.build_parent_based_families()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a GEDCOM file from 23andMe family data.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Path to the directory with input JSON files.")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / ".." / "output" / "export.ged", help="Output GEDCOM file path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output.")

    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tree_nodes, annotations, relatives = load_data(args.data_dir)
    exporter = GedcomExporter(tree_nodes, annotations, relatives, verbose=not args.quiet)
    exporter.export(args.output)

    if exporter.verbose:
        print(f"[✓] GEDCOM export complete: {args.output.resolve()}")