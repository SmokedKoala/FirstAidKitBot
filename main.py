import json
import sys
from typing import Any

import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup
from pyzbar.pyzbar import decode

USER_AGENT = (
    "FirstAidKitBot/1.0 (medicine barcode lookup; local use; not medical advice)"
)


def is_ean13(symbology: str) -> bool:
    """pyzbar reports EAN-13 as 'EAN13'."""
    return symbology.upper().replace("-", "") == "EAN13"


def symbology_str(barcode: Any) -> str:
    t = barcode.type
    return t.decode() if isinstance(t, bytes) else str(t)


def _abs_medum_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"https://medum.ru{href}"
    return f"https://medum.ru/{href}"


def lookup_medum_ru(gtin: str) -> dict[str, Any] | None:
    """GET https://medum.ru/{gtin} and parse product / registration lines."""
    gtin = gtin.strip()
    if not gtin.isdigit():
        return None
    url = f"https://medum.ru/{gtin}"
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru,en;q=0.9",
            },
            timeout=25,
        )
        r.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    root = soup.find("div", id="barcodes")
    if not root:
        return None

    head = root.find("div", class_="head")
    barcode_label = None
    if head:
        span = head.find("span")
        if span:
            barcode_label = span.get_text(strip=True)

    products: list[dict[str, str]] = []
    prod_div = root.find("div", class_="products")
    if prod_div:
        for a in prod_div.select("ol li a"):
            name = a.get_text(strip=True)
            if not name:
                continue
            products.append(
                {
                    "name": name,
                    "url": _abs_medum_url(a.get("href")) or "",
                }
            )

    certificates: list[dict[str, str]] = []
    cert_div = root.find("div", class_="certificates")
    if cert_div:
        seen: set[tuple[str, str, str]] = set()
        for li in cert_div.find_all("li"):
            a = li.find("a")
            p = li.find("p")
            reg = a.get_text(strip=True) if a else ""
            href = a.get("href") if a else None
            date_note = p.get_text(strip=True) if p else ""
            key = (reg, href or "", date_note)
            if key in seen:
                continue
            seen.add(key)
            certificates.append(
                {
                    "registration": reg,
                    "url": _abs_medum_url(href) or "",
                    "date_note": date_note,
                }
            )

    if not products and not certificates and not barcode_label:
        return None

    return {
        "source": "Medum.ru (справочная информация; не медицинская консультация)",
        "page_url": url,
        "barcode_kind": barcode_label,
        "products": products,
        "registration_certificates": certificates,
    }


def scan_image_bgr(img: np.ndarray) -> dict[str, Any]:
    """Decode all barcodes from a BGR image (OpenCV). Returns JSON-serializable dict."""
    items: list[dict[str, Any]] = []
    for barcode in decode(img):
        if not barcode.data:
            continue
        try:
            code = barcode.data.decode("utf-8")
        except UnicodeDecodeError:
            code = barcode.data.decode("latin-1", errors="replace")

        sym = symbology_str(barcode)
        r = barcode.rect
        entry: dict[str, Any] = {
            "data": code,
            "symbology": sym,
            "rect": {
                "x": r.left,
                "y": r.top,
                "width": r.width,
                "height": r.height,
            },
        }

        if is_ean13(sym):
            medum = lookup_medum_ru(code)
            entry["medum"] = medum
            entry["medum_url"] = f"https://medum.ru/{code}"
            if medum is None:
                entry["medum_note"] = "no_barcode_block_or_request_failed"
        else:
            entry["medum"] = None
            entry["medum_note"] = "skipped_not_ean13"

        items.append(entry)

    return {"barcodes": items}


def scan_image_bytes(data: bytes) -> dict[str, Any]:
    """Decode image file bytes (JPEG, PNG, etc.) and scan barcodes."""
    if not data:
        return {"error": "empty_body", "barcodes": []}
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "invalid_or_unsupported_image", "barcodes": []}
    out = scan_image_bgr(img)
    return out


def print_product_info(info: dict[str, Any]) -> None:
    print("\n--- Medum.ru ---")
    for key, val in info.items():
        if val is None or val == "" or val == []:
            continue
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False, indent=2)
        print(f"  {key}: {val}")


def BarcodeReader(image: str) -> None:
    img = cv2.imread(image)
    if img is None:
        print(f"Could not read image: {image}")
        return

    result = scan_image_bgr(img)
    if not result["barcodes"]:
        print("Barcode Not Detected or your barcode is blank/corrupted!")
        return

    for item in result["barcodes"]:
        x, y, w, h = (
            item["rect"]["x"],
            item["rect"]["y"],
            item["rect"]["width"],
            item["rect"]["height"],
        )
        cv2.rectangle(
            img,
            (x - 10, y - 10),
            (x + w + 10, y + h + 10),
            (255, 0, 0),
            2,
        )

        print(f"\nDecoded: {item['data']}")
        print(f"Symbology: {item['symbology']}")

        if not is_ean13(item["symbology"]):
            print(
                "Medum.ru lookup runs only for EAN-13 barcodes "
                f"(https://medum.ru/<code>)."
            )
            continue

        medum = item.get("medum")
        if medum:
            print_product_info(medum)
        else:
            print(
                "\nMedum.ru: no barcode card in HTML (or request failed). "
                f"Open manually: https://medum.ru/{item['data']}"
            )

    cv2.imshow("Image", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        BarcodeReader(sys.argv[1])
    else:
        from app import start

        start()
