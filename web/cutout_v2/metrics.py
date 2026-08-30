"""Alpha-/Masken-Metriken für Gold-Eval und QA (ohne Collection zu ändern)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


SERO_ICE_BLUE = (245, 249, 255)


def load_alpha(path: Path | str) -> tuple[np.ndarray, np.ndarray]:
    im = Image.open(path)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    arr = np.asarray(im, dtype=np.uint8)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3].astype(np.float64) / 255.0
    return rgb, alpha


def sha256_file(path: Path | str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def binary_mask(alpha: np.ndarray, thresh: float = 0.04) -> np.ndarray:
    return alpha > thresh


def iou(pred: np.ndarray, gt: np.ndarray) -> float:
    inter = np.logical_and(pred, gt).sum()
    union = np.logical_or(pred, gt).sum()
    return float(inter / union) if union else 1.0


def dice(pred: np.ndarray, gt: np.ndarray) -> float:
    inter = np.logical_and(pred, gt).sum()
    s = pred.sum() + gt.sum()
    return float(2 * inter / s) if s else 1.0


def boundary_f1(pred: np.ndarray, gt: np.ndarray, width: int = 2) -> float:
    from scipy import ndimage

    def edge(m):
        dil = ndimage.binary_dilation(m, iterations=width)
        ero = ndimage.binary_erosion(m, iterations=width)
        return np.logical_and(dil, np.logical_not(ero))

    pe, ge = edge(pred), edge(gt)
    tp = np.logical_and(pe, ge).sum()
    fp = np.logical_and(pe, np.logical_not(ge)).sum()
    fn = np.logical_and(ge, np.logical_not(pe)).sum()
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    return float(2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0


def sad_mse(pred_a: np.ndarray, gt_a: np.ndarray) -> tuple[float, float]:
    d = pred_a.astype(np.float64) - gt_a.astype(np.float64)
    return float(np.abs(d).sum()), float((d * d).mean())


def connectivity_score(alpha: np.ndarray, thresh: float = 0.04) -> dict[str, Any]:
    from scipy import ndimage
    mask = binary_mask(alpha, thresh)
    labeled, n = ndimage.label(mask)
    sizes = [int((labeled == i).sum()) for i in range(1, n + 1)]
    sizes.sort(reverse=True)
    return {
        "components": int(n),
        "largest_frac": float(sizes[0] / mask.size) if sizes else 0.0,
        "sizes": sizes[:8],
    }


def margin_stats(alpha: np.ndarray, thresh: float = 0.04) -> dict[str, Any]:
    h, w = alpha.shape
    mask = binary_mask(alpha, thresh)
    if not mask.any():
        return {
            "empty": True,
            "transparent_frac": 1.0,
            "fully_transparent_frac": float((alpha < 0.004).mean()),
            "canvas_touch": False,
            "pad": {"t": 0.0, "b": 0.0, "l": 0.0, "r": 0.0},
            "pad_px": {"t": 0, "b": 0, "l": 0, "r": 0},
            "bbox": None,
            "fg_frac": 0.0,
            "aspect": None,
            "bbox_area_frac": 0.0,
        }
    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    pad_px = {"t": y0, "b": h - 1 - y1, "l": x0, "r": w - 1 - x1}
    pad = {
        "t": pad_px["t"] / h,
        "b": pad_px["b"] / h,
        "l": pad_px["l"] / w,
        "r": pad_px["r"] / w,
    }
    touch = pad_px["t"] == 0 or pad_px["b"] == 0 or pad_px["l"] == 0 or pad_px["r"] == 0
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    return {
        "empty": False,
        "transparent_frac": float(1.0 - mask.mean()),
        "fully_transparent_frac": float((alpha < 0.004).mean()),
        "canvas_touch": bool(touch),
        "pad": pad,
        "pad_px": pad_px,
        "bbox": [x0, y0, x1, y1],
        "fg_frac": float(mask.mean()),
        "aspect": round(bh / max(bw, 1), 4),
        "bbox_area_frac": float((bw * bh) / (w * h)),
    }


def rectangularity(alpha: np.ndarray, thresh: float = 0.04) -> float:
    mask = binary_mask(alpha, thresh)
    if not mask.any():
        return 0.0
    ys, xs = np.where(mask)
    box = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return float(box.mean()) if box.size else 0.0


def gradient_edge_energy(alpha: np.ndarray) -> float:
    gy, gx = np.gradient(alpha.astype(np.float64))
    return float(np.hypot(gx, gy).mean())


def compose_on_color(rgba: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    bg = Image.new("RGBA", rgba.size, rgb + (255,))
    return Image.alpha_composite(bg, rgba.convert("RGBA")).convert("RGB")


def checkerboard(size: tuple[int, int], cell: int = 24) -> Image.Image:
    w, h = size
    im = Image.new("RGB", (w, h), (220, 220, 220))
    px = im.load()
    for y in range(h):
        for x in range(w):
            if ((x // cell) + (y // cell)) % 2:
                px[x, y] = (180, 180, 180)
    return im


def compose_on_checker(rgba: Image.Image) -> Image.Image:
    board = checkerboard(rgba.size).convert("RGBA")
    return Image.alpha_composite(board, rgba.convert("RGBA")).convert("RGB")


RENDER_BACKGROUNDS = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "magenta": (255, 0, 255),
    "sero_ice": SERO_ICE_BLUE,
}


def render_preview_set(rgba_path: Path, dest_dir: Path) -> dict[str, str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    rgba = Image.open(rgba_path).convert("RGBA")
    out: dict[str, str] = {}
    for name, color in RENDER_BACKGROUNDS.items():
        p = dest_dir / f"on_{name}.jpg"
        compose_on_color(rgba, color).save(p, quality=90)
        out[name] = str(p)
    p = dest_dir / "on_checker.jpg"
    compose_on_checker(rgba).save(p, quality=90)
    out["checker"] = str(p)
    return out


def analyze_cutout(path: Path | str, gt_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(path)
    rgb, alpha = load_alpha(path)
    m = margin_stats(alpha)
    conn = connectivity_score(alpha)
    report: dict[str, Any] = {
        "path": str(path),
        "size": [int(alpha.shape[1]), int(alpha.shape[0])],
        "mode": Image.open(path).mode,
        "fully_transparent_frac": m["fully_transparent_frac"],
        "transparent_frac": m["transparent_frac"],
        "fg_frac": m["fg_frac"],
        "canvas_touch": m["canvas_touch"],
        "pad": m["pad"],
        "pad_px": m["pad_px"],
        "bbox": m["bbox"],
        "aspect": m["aspect"],
        "bbox_area_frac": m.get("bbox_area_frac"),
        "rectangularity": rectangularity(alpha),
        "components": conn["components"],
        "largest_frac": conn["largest_frac"],
        "gradient_energy": gradient_edge_energy(alpha),
        "nearly_opaque": bool(m["fully_transparent_frac"] < 0.01),
        "corners_alpha": [
            float(alpha[0, 0]),
            float(alpha[0, -1]),
            float(alpha[-1, 0]),
            float(alpha[-1, -1]),
        ],
    }
    if gt_path and Path(gt_path).exists():
        _, gt_a = load_alpha(gt_path)
        if gt_a.shape != alpha.shape:
            gt_im = Image.fromarray((gt_a * 255).astype(np.uint8), mode="L")
            gt_im = gt_im.resize((alpha.shape[1], alpha.shape[0]), Image.NEAREST)
            gt_a = np.asarray(gt_im, dtype=np.float64) / 255.0
        pred_m = binary_mask(alpha)
        gt_m = binary_mask(gt_a)
        sad, mse = sad_mse(alpha, gt_a)
        report["vs_gt"] = {
            "iou": iou(pred_m, gt_m),
            "dice": dice(pred_m, gt_m),
            "boundary_f1": boundary_f1(pred_m, gt_m),
            "sad": sad,
            "mse": mse,
        }
    return report
