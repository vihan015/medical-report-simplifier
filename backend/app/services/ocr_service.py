"""OCR for scanned PDFs and images. Tesseract (default) or PaddleOCR."""
import io
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class OCRUnavailable(RuntimeError):
    pass


def _preprocess(data: bytes):
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("L")
    if min(img.size) < 1200:  # small phone photos / thumbnails OCR badly
        scale = 1200 / min(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return ImageOps.autocontrast(img)


class OCRService:
    def __init__(self, engine: str = "tesseract", langs: str = "eng"):
        self.engine = engine.lower()
        self.langs = langs
        self._paddle = None

    def available(self) -> bool:
        try:
            if self.engine == "paddle":
                import paddleocr  # noqa: F401
                return True
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def ocr_image_bytes(self, data: bytes) -> tuple[str, float]:
        """Returns (text, mean_confidence 0..1)."""
        img = _preprocess(data)
        if self.engine == "paddle":
            return self._paddle_ocr(img)
        return self._tesseract_ocr(img)

    def _tesseract_ocr(self, img) -> tuple[str, float]:
        try:
            import pytesseract
            from pytesseract import Output

            d = pytesseract.image_to_data(
                img, lang=self.langs, output_type=Output.DICT,
                config="--psm 6 -c preserve_interword_spaces=1",
            )
        except Exception as e:
            raise OCRUnavailable(f"Tesseract OCR failed: {e}") from e
        lines: dict[tuple, list[tuple[int, str]]] = defaultdict(list)
        confs = []
        for i, word in enumerate(d["text"]):
            if not word.strip():
                continue
            conf = float(d["conf"][i])
            if conf >= 0:
                confs.append(conf)
            lines[(d["block_num"][i], d["par_num"][i], d["line_num"][i])].append((d["left"][i], word))
        text = "\n".join(" ".join(w for _, w in sorted(ws)) for _, ws in sorted(lines.items()))
        return text, (sum(confs) / len(confs) / 100.0 if confs else 0.0)

    def _paddle_ocr(self, img) -> tuple[str, float]:
        try:
            import numpy as np
            from paddleocr import PaddleOCR

            if self._paddle is None:
                self._paddle = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            result = self._paddle.ocr(np.array(img.convert("RGB")), cls=True)
        except Exception as e:
            raise OCRUnavailable(f"PaddleOCR failed: {e}") from e
        boxes = []
        for line in (result[0] or []):
            pts, (txt, conf) = line
            ys = [p[1] for p in pts]
            xs = [p[0] for p in pts]
            boxes.append(((min(ys) + max(ys)) / 2, min(xs), txt, float(conf), max(ys) - min(ys)))
        boxes.sort()
        rows: list[list] = []
        for b in boxes:
            if rows and abs(b[0] - rows[-1][-1][0]) <= max(6.0, b[4] * 0.5):
                rows[-1].append(b)
            else:
                rows.append([b])
        text = "\n".join(" ".join(x[2] for x in sorted(r, key=lambda b: b[1])) for r in rows)
        confs = [b[3] for b in boxes]
        return text, (sum(confs) / len(confs) if confs else 0.0)
