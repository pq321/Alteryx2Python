# Local vision adapters

`local_vision` exposes conservative local profiles for Barcode and ImageToText.
Barcode uses an installed OpenCV barcode detector; OCR uses an installed
Tesseract executable plus `pytesseract`.

ImageTemplate, ImageRecognition, and KeyValuePairExtraction are listed in the
module's `UNAVAILABLE` metadata because their native annotation/model runtimes
are not bundled. No network access or automatic model download is performed.
Outputs are local evidence only and do not claim native Alteryx equivalence.
