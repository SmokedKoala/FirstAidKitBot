import sys
from scan import (
    barcode_reader,
    is_ean13,
    lookup_medum_ru,
    print_product_info,
    scan_image_bgr,
    scan_image_bytes,
    symbology_str,
)

# Backward-compatible alias for existing external imports/usages.
BarcodeReader = barcode_reader


if __name__ == "__main__":
    if len(sys.argv) > 1:
        barcode_reader(sys.argv[1])
    else:
        from app import start

        start()
