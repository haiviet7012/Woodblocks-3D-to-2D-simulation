"""Các metric ảnh phục vụ nghiên cứu nét khắc.

E_net là metric ứng viên, chưa phải thước đo OCR đã kiểm chứng.
"""

import cv2
import numpy as np


def measure(
    rgb,
    stroke,
    valid,
    roi=None,
    sigma=1.0,
    band=2,
    eps=1e-3,
):
    """
    Parameters
    ----------
    rgb : uint8, H x W x 3
        Ảnh RGB cuối cùng.
    stroke : H x W
        Mask nét chữ.
    valid : H x W
        Mask pixel thuộc vật thể.
    roi : H x W hoặc None
        Vùng chữ cần đo.
    sigma : float
        Sigma Gaussian trước khi tính gradient.
    band : int
        Bề rộng dải biên, tính theo pixel.
    eps : float
        Hệ số ổn định mẫu số trên thang ảnh [0, 1].

    Returns
    -------
    dict
        E_net, gradient biên/nền, Laplacian và Tenengrad.
        E_net=None khi thiếu vùng đo.
    """
    rgb = np.asarray(rgb)

    if rgb.dtype != np.uint8:
        raise ValueError("rgb phải có dtype uint8, giá trị 0–255.")

    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("rgb phải có kích thước H x W x 3.")

    if sigma <= 0 or band < 1 or eps <= 0:
        raise ValueError("Cần sigma > 0, band >= 1, eps > 0.")

    band = int(band)
    shape = rgb.shape[:2]

    # copy để không sửa mask đầu vào của notebook.
    stroke = np.asarray(stroke, dtype=bool).copy()
    valid = np.asarray(valid, dtype=bool).copy()

    if stroke.shape != shape or valid.shape != shape:
        raise ValueError("stroke/valid phải cùng kích thước ảnh.")

    if roi is not None:
        roi = np.asarray(roi, dtype=bool)

        if roi.shape != shape:
            raise ValueError("roi phải cùng kích thước ảnh.")

        valid &= roi

    gray = cv2.cvtColor(
        rgb, cv2.COLOR_RGB2GRAY
    ).astype(np.float32) / 255.0

    kernel = np.ones((3, 3), dtype=np.uint8)

    # Loại vùng gần biên vật thể/ROI để tránh gradient giả.
    margin = max(
        band + 2,
        int(np.ceil(3 * sigma)) + 1,
    )

    support = cv2.erode(
        valid.astype(np.uint8),
        kernel,
        iterations=margin,
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    ).astype(bool)

    s = stroke.astype(np.uint8)

    outer = cv2.dilate(
        s, kernel, iterations=band
    ).astype(bool)

    inner = cv2.erode(
        s, kernel, iterations=band
    ).astype(bool)

    edge = outer & ~inner & support

    near = cv2.dilate(
        s, kernel, iterations=5 * band
    ).astype(bool)

    excluded = cv2.dilate(
        s, kernel, iterations=2 * band
    ).astype(bool)

    background = near & ~excluded & support

    result = {
        "metric_version": "enet-v0.1",
        "status": "insufficient_support",
        "E_net": None,
        "edge_gradient": None,
        "background_gradient": None,
        "laplacian_var": None,
        "tenengrad": None,
        "edge_pixels": int(edge.sum()),
        "background_pixels": int(background.sum()),
        "support_pixels": int(support.sum()),
        "sigma_px": float(sigma),
        "band_px": band,
        "eps": float(eps),
    }

    if support.sum() < 32:
        return result

    smooth = cv2.GaussianBlur(
        gray, (0, 0), sigmaX=sigma, sigmaY=sigma
    )

    gx = cv2.Sobel(
        smooth, cv2.CV_32F,
        1, 0, ksize=3, scale=1 / 8,
    )

    gy = cv2.Sobel(
        smooth, cv2.CV_32F,
        0, 1, ksize=3, scale=1 / 8,
    )

    gradient = np.hypot(gx, gy)

    lap = cv2.Laplacian(
        gray, cv2.CV_32F, ksize=3
    )

    result["laplacian_var"] = float(
        lap[support].var()
    )

    result["tenengrad"] = float(
        np.mean(gradient[support] ** 2)
    )

    if edge.sum() < 32 or background.sum() < 32:
        return result

    ge = float(np.median(gradient[edge]))
    gb = float(np.median(gradient[background]))

    result.update({
        "status": "ok",
        "E_net": ge / (gb + eps),
        "edge_gradient": ge,
        "background_gradient": gb,
    })

    return result