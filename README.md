# 23andMe Family Tree Scraper & GEDCOM Exporter

This project lets you scrape your family tree data from 23andMe and convert it into a GEDCOM file, which can be imported into genealogy software like Gramps, Ancestry, or MyHeritage.

## 🔍 Features

- Scrapes family tree data from 23andMe (including relatives, nodes, and annotations)
- Normalizes and processes data into standard GEDCOM format
- Command-line interface with flexible output options


## 📦 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/23andMeFamilyTreeScraper.git
   cd 23andMeFamilyTreeScraper
   ```

2. Set up a virtual environment (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   # If you use uv (recommended)
   uv pip install

   # Or with standard pip:
   pip install .  # This installs using pyproject.toml metadata
   ```

## 🚀 Usage

### Option 1: Run the full pipeline (scrape + GEDCOM export)

```bash
python main.py
```

This will:
- Scrape your family tree data from 23andMe (you may need to authenticate)
- Store JSON files in the `data/` folder
- Export a `export.ged` file in the `output/` folder

### Option 2: Generate GEDCOM from existing JSON

If you’ve already scraped data, you can run:

```bash
python src/gedcom_generator.py --data-dir data --output output/tree.ged
```

## 🧪 Testing

Run the included unit tests:

```bash
pytest -v
```

## 📂 Output

The GEDCOM file will be saved to `output/export.ged` by default and can be opened in any genealogy software that supports GEDCOM 5.5.1.

## 📜 License

MIT License. See `LICENSE` file for details.

## 🙋‍♂️ Author

Built by Boris Legradic as a personal side project to preserve family history. Contributions welcome!

### Environment setup example with uv

If you are using [`uv`](https://github.com/astral-sh/uv) for fast Python dependency management:

```bash
uv venv
source .venv/bin/activate
uv pip install 
```

### Or with pip:

```bash
python3 -m venv venv
source venv/bin/activate
pip install .  
```
