"""Xuất bản đồ hình học cùng camera với ảnh render.

Yêu cầu Mitsuba variant vector hóa: LLVM hoặc CUDA.
"""

import numpy as np


def geometry_maps(
    item,
    cam,
    mi,
    scene,
    chunk=131072,
):
    """
    Parameters
    ----------
    item : dict
        Item trong ITEMS của notebook.
    cam : dict
        Camera do make_camera() của notebook tạo.
    mi
        Module Mitsuba đang dùng trong notebook.
    scene
        Scene chỉ chứa mesh vật thể.
        Truyền occlusion_scene(item["ply"]).
    chunk : int
        Số tia xử lý mỗi lượt.

    Returns
    -------
    depth : H x W, float32
        Camera-z, mét; NaN ngoài vật thể.
    normals : H x W x 3, float32
        Pháp tuyến hình học trong hệ tọa độ thế giới.
    valid : H x W, bool
        Pixel có giao điểm với vật thể.
    stroke : H x W, bool
        Mask nét chiếu vào camera; nếu chỉ có raised,
        đây là mask proxy, chưa phải ground truth.
    """
    variant = mi.variant()

    if variant is None or variant.startswith("scalar"):
        raise RuntimeError(
            "geometry_maps cần LLVM/CUDA. "
            f"Variant hiện tại: {variant}"
        )

    if chunk < 1:
        raise ValueError("chunk phải >= 1.")

    H = int(cam["H"])
    W = int(cam["W"])

    K = np.asarray(cam["K"], dtype=np.float64)
    R = np.asarray(cam["R"], dtype=np.float64)
    t = np.asarray(cam["t"], dtype=np.float64)
    origin = np.asarray(
        cam["origin"], dtype=np.float64
    )

    K_inv = np.linalg.inv(K)

    depth = np.full(
        (H, W), np.nan, dtype=np.float32
    )

    position = np.full(
        (H, W, 3), np.nan, dtype=np.float32
    )

    normals = np.full(
        (H, W, 3), np.nan, dtype=np.float32
    )

    valid = np.zeros((H, W), dtype=bool)

    def vector_to_numpy(vector):
        # Đọc từng thành phần để tránh nhầm layout N×3/3×N.
        return np.column_stack([
            np.asarray(vector[j]).reshape(-1)
            for j in range(3)
        ])

    for start in range(0, H * W, chunk):
        idx = np.arange(
            start, min(start + chunk, H * W)
        )

        # Quy ước notebook: tâm pixel là (x+0.5, y+0.5).
        pixels = np.column_stack([
            idx % W + 0.5,
            idx // W + 0.5,
            np.ones(len(idx)),
        ])

        directions = (pixels @ K_inv.T) @ R

        directions /= np.linalg.norm(
            directions, axis=1, keepdims=True
        )

        ray_origins = np.broadcast_to(
            origin, directions.shape
        )

        ray = mi.Ray3f(
            mi.Point3f(
                ray_origins[:, 0].copy(),
                ray_origins[:, 1].copy(),
                ray_origins[:, 2].copy(),
            ),
            mi.Vector3f(
                directions[:, 0].copy(),
                directions[:, 1].copy(),
                directions[:, 2].copy(),
            ),
        )

        interaction = scene.ray_intersect(ray)

        hit = np.asarray(
            interaction.is_valid()
        ).reshape(-1).astype(bool)

        points = vector_to_numpy(interaction.p)
        ns = vector_to_numpy(interaction.n)

        good_indices = idx[hit]

        position.reshape(-1, 3)[good_indices] = points[hit]
        normals.reshape(-1, 3)[good_indices] = ns[hit]

        camera_points = points[hit] @ R.T + t

        depth.reshape(-1)[good_indices] = (
            camera_points[:, 2]
        )

        valid.reshape(-1)[idx] = hit

    # Ưu tiên mask nét được gán/kiểm chứng.
    source = item.get("stroke_mask_uv")

    if source is None:
        source = item.get("raised")

    stroke = np.zeros((H, W), dtype=bool)

    if source is not None:
        source = np.asarray(source)

        if source.ndim != 2 or source.size == 0:
            raise ValueError(
                "stroke_mask_uv/raised phải là mask 2D không rỗng."
            )

        lo, hi = np.asarray(item["mesh"].bounds)

        if hi[0] <= lo[0] or hi[1] <= lo[1]:
            raise ValueError("Mesh không có miền UV phẳng hợp lệ.")

        points = position[valid]

        # Cùng quy ước raised_mask_uv() trong notebook:
        # cột 0 = x nhỏ nhất; hàng 0 = y lớn nhất.
        u = (
            (points[:, 0] - lo[0])
            / (hi[0] - lo[0])
            * source.shape[1]
        )

        v = (
            (hi[1] - points[:, 1])
            / (hi[1] - lo[1])
            * source.shape[0]
        )

        u = np.clip(
            np.floor(u).astype(np.int64),
            0, source.shape[1] - 1,
        )

        v = np.clip(
            np.floor(v).astype(np.int64),
            0, source.shape[0] - 1,
        )

        stroke[valid] = source[v, u] > 0.5

    return depth, normals, valid, stroke