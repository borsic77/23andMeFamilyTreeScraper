import json
from pathlib import Path
from datetime import datetime
import pytest

# Import the functions and classes to be tested
from src.gedcom_generator import normalize_tree_nodes, GedcomIdGenerator, GedcomExporter, load_data

# Test normalization of tree nodes
def test_normalize_tree_nodes():
    # Minimal sample: two nodes, one with profile_id
    sample_nodes = [
        {"id": "1", "first_name": "Alice", "parent_ids": [], "partner_ids": []},
        {"id": "2", "profile_id": "A2", "first_name": "Bob", "parent_ids": ["1"], "partner_ids": []}
    ]
    normalized = normalize_tree_nodes(sample_nodes)
    # Expect keys: "1" for first node and "A2" for second node
    assert "1" in normalized
    assert "A2" in normalized
    # Check that the parent_ids have been normalized: for Bob, parent_ids should remain "1"
    assert normalized["A2"]["parent_ids"] == ["1"]

# Test basic functionality of GedcomIdGenerator
def test_gedcom_id_generator():
    gen = GedcomIdGenerator()
    id1 = gen.get_gedcom_id("key1")
    id2 = gen.get_gedcom_id("key1")
    id3 = gen.get_gedcom_id("key2")
    assert id1 == id2  # Same key should yield the same ID
    assert id1 != id3  # Different keys should yield different IDs

    # Test family ID generation
    fid1 = gen.new_family_id()
    fid2 = gen.new_family_id()
    assert fid1 != fid2

# Create a fixture for minimal data using pytest's tmp_path
@pytest.fixture
def minimal_data(tmp_path: Path):
    # Create minimal JSON structures for testing
    tree_nodes = [
        {"id": "1", "first_name": "Alice", "partner_ids": ["2"], "parent_ids": []},
        {"id": "2", "first_name": "Bob", "partner_ids": ["1"], "parent_ids": []}
    ]
    annotations = [
        {"tree_node_id": "1", "first_name": "Alice", "last_name": "Smith", "sex": "F"},
        {"tree_node_id": "2", "first_name": "Bob", "last_name": "Jones", "sex": "M"}
    ]
    relatives = []  # Empty for this minimal test

    # Save these into temporary files for load_data
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "tree.json").write_text(json.dumps(tree_nodes))
    (data_dir / "annotations.json").write_text(json.dumps(annotations))
    (data_dir / "relatives_10.json").write_text(json.dumps(relatives))
    return data_dir

# Test the GEDCOM export with minimal data
def test_export_minimal(minimal_data: Path, tmp_path: Path):
    # Load the minimal data
    tree_nodes, annotations, relatives = load_data(minimal_data)
    exporter = GedcomExporter(tree_nodes, annotations, relatives, verbose=False)
    lines = exporter.generate_gedcom_lines()

    # Check that the export starts with HEAD and ends with TRLR
    assert lines[0].startswith("0 HEAD")
    assert lines[-1] == "0 TRLR"

    # Check that individual entries exist (at least two)
    indi_lines = [line for line in lines if "INDI" in line]
    assert len(indi_lines) >= 2

if __name__ == "__main__":
    pytest.main(["-v"])