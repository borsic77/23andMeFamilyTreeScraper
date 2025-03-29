from src.scraper import run_scraper
from src.gedcom_generator import load_data, GedcomExporter
from pathlib import Path

def main():
    print("Starting 23andMe family tree scraping and GEDCOM export...")

    data_dir = Path(__file__).parent / "data"
    output_path = Path(__file__).parent / "output" / "export.ged"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_scraper(data_dir)  # Save JSON files into the data directory

    tree_nodes, annotations, relatives = load_data(data_dir)
    exporter = GedcomExporter(tree_nodes, annotations, relatives)
    exporter.export(output_path)

    print(f"Export complete. GEDCOM file saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
