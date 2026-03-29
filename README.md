# FirstAidKitBot

A small Python utility that reads **EAN-13** barcodes from an image file, requests the matching page on **[Medum.ru](https://medum.ru/)** (Russian drug reference), and prints structured data parsed from the HTML: linked product names and registration certificates when the site exposes them.

Information from Medum.ru is **reference-only** and is **not** medical advice, diagnosis, or treatment. Always follow a qualified professional’s guidance and the official labeling for your product.

## Requirements

- Python 3.10+ (uses `str | None` style typing)
- System libraries for **ZBar** (used by `pyzbar` to decode barcodes). On Windows, install a ZBar build and ensure DLLs are on your `PATH`, or use a Python environment where `pyzbar` is already working.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

By default this opens `photo_2026-03-28_15-05-13.jpg` in the project folder. Pass another image path:

```bash
python main.py path/to/photo.jpg
```

The script draws a box around each detected barcode, prints the decoded value and symbology, and:

- For **EAN-13**: fetches `https://medum.ru/<digits>` and prints product links and registration lines when present.
- For **other symbologies** (e.g. Code128): prints a short note that only EAN-13 is looked up on Medum.ru.

## How it works

1. **OpenCV** loads the image; **pyzbar** decodes barcodes.
2. If the symbology is EAN-13, **requests** loads the Medum barcode page.
3. **BeautifulSoup** parses the `#barcodes` block: product names (`div.products`) and registration certificates (`div.certificates`).

If the page has no barcode block or the request fails, the script suggests opening the same URL in a browser.

## License / data

This project does not redistribute Medum.ru content; it only fetches public pages at runtime. Respect [Medum.ru](https://medum.ru/) terms of use and rate limits for your use case.
