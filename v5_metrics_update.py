# -*- coding: utf-8 -*-
"""Update V5 after cell12.5, before cell13, through exec(..., globals()).
Notebook dependencies are explicitly checked and bound below.
No notebook file is rewritten; no dependencies are installed; no OCR runs.
Generated masks remain unvalidated until a reviewer approves them.
"""
from pathlib import Path as _PatchPath
import hashlib as _patch_hashlib

_notebook = globals()
_required = (
    "cfg", "ROOT", "RUN_ID", "NOTEBOOK_SOURCE_SHA256", "mi",
    "sample_camera", "sample_lights", "get_profile_config",
    "get_data_profile", "get_detail_level", "occlusion_scene",
)
_missing = [name for name in _required if name not in _notebook]
if _missing:
    raise RuntimeError(
        "Run notebook through cell12.5 before loading this update. Missing: "
        + ", ".join(_missing)
    )

# Explicit bindings support both runtime validation and VS Code analysis.
cfg = _notebook["cfg"]
ROOT = _notebook["ROOT"]
RUN_ID = _notebook["RUN_ID"]
NOTEBOOK_SOURCE_SHA256 = _notebook["NOTEBOOK_SOURCE_SHA256"]
mi = _notebook["mi"]
occlusion_scene = _notebook["occlusion_scene"]
get_data_profile = _notebook["get_data_profile"]
get_detail_level = _notebook["get_detail_level"]

# Restore original functions so repeated loading cannot wrap a wrapper recursively.
sample_camera = _notebook.get("_sample_camera_base", _notebook["sample_camera"])
sample_lights = _notebook.get("_sample_lights_base", _notebook["sample_lights"])
get_profile_config = _notebook.get("_get_profile_config_base", _notebook["get_profile_config"])

_patch_path_value = _notebook.get("PATCH_PATH")
if _patch_path_value is None:
    raise RuntimeError("Set PATCH_PATH in the notebook before exec().")
METRICS_PATCH_SHA256 = _patch_hashlib.sha256(
    _PatchPath(_patch_path_value).read_bytes()
).hexdigest()

"""Research output contract for WoodblockSynth. Draft metric implementation, not Son's official code.

All masks are boolean in camera pixel space unless suffixed _uv. UV rows run
from maximum Y to minimum Y on the normalized mesh; columns run minimum X to maximum X.
"""
from pathlib import Path
from dataclasses import dataclass, asdict
import csv
import hashlib
import importlib.util
import json
import time
import numpy as np
import cv2

PIPELINE_VERSION = 'v5_son_pdf_update_1.0'
SCHEMA_VERSION = 'woodblock.sample.1.0'
METRIC_VERSION = 'son_pdf_20261105_draft_reference_2.0'  # deliberately NOT Son's 1.0.0


METRIC_REGISTRY = {'lap_global': {'role': 'image_quality', 'requires': 'object_mask'}, 'lap_local': {'role': 'image_quality', 'requires': 'reviewed_roi'}, 'ec_2d': {'role': 'edge_contrast', 'requires': 'reviewed_roi'}, 'ec_3d': {'role': 'stroke_edge_contrast', 'requires': 'reviewed_stroke_and_roi'}, 'E_net': {'role': 'compatibility_alias', 'alias_of': 'ec_3d'}, 'E_proxy': {'role': 'diagnostic_only'}, 'ec_3d_proxy': {'role': 'diagnostic_alias', 'alias_of': 'E_proxy'}, 'edge_f1': {'role': 'diagnostic_edge_agreement', 'requires': 'reviewed_stroke_and_roi'}}

@dataclass
class MetricConfig:
    sigma_px: float = 1.0
    band_radius_px: int = 1
    background_gap_px: int = 1
    support_margin_px: int = 4
    eps: float = 0.5 / 255.0
    min_pixels: int = 32
    canny_low_quantile: float = 0.70
    canny_high_quantile: float = 0.90
    f1_tolerance_px: int = 2


def clean_json(x):
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean_json(v) for v in x]
    if isinstance(x, np.ndarray):
        return clean_json(x.tolist())
    if isinstance(x, np.generic):
        return clean_json(x.item())
    if isinstance(x, Path):
        return str(x)
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(clean_json(data), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def init_output(root):
    root = Path(root)
    for name in ('images', 'render_images', 'masks', 'edge_maps', 'geometry', 'overlays',
                 'logs', 'labels', 'patches', 'assets', 'selftest', 'rejected'):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def morph(mask, radius, operation='dilate'):
    a = np.asarray(mask, np.uint8)
    if radius == 0:
        return a.astype(bool)
    kernel = np.ones((2 * int(radius) + 1,) * 2, np.uint8)
    fn = cv2.dilate if operation == 'dilate' else cv2.erode
    return fn(a, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)


def read_mask(path, shape):
    a = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if a is None or tuple(a.shape) != tuple(shape):
        raise ValueError('Mask missing or shape mismatch: ' + str(path))
    if not set(np.unique(a)).issubset({0,1,255}):
        raise ValueError('Expected a binary mask (0/1 or 0/255): '+str(path))
    return a > 0


def board_height_grid(item, mi, scene, texel_mm=0.20, max_side=4096):
    lo, hi = np.asarray(item['mesh'].bounds, float)
    ext = hi - lo
    ppm = min(1.0 / texel_mm, max_side / (max(ext[:2]) * 1000.0))
    W, H = np.maximum(8, np.ceil(ext[:2] * 1000.0 * ppm).astype(int))
    x = lo[0] + (np.arange(W) + .5) / W * ext[0]
    y = hi[1] - (np.arange(H) + .5) / H * ext[1]
    z = np.full((H, W), np.nan, np.float32)
    for r0 in range(0, H, max(1, 262144 // W)):
        r1 = min(H, r0 + max(1, 262144 // W))
        X, Y = np.meshgrid(x, y[r0:r1])
        ray = mi.Ray3f(mi.Point3f(X.ravel().copy(), Y.ravel().copy(), np.full(X.size, hi[2] + .05)),
                       mi.Vector3f(np.zeros(X.size), np.zeros(X.size), -np.ones(X.size)))
        t = np.asarray(scene.ray_intersect(ray).t).reshape(X.shape)
        z[r0:r1] = np.where(np.isfinite(t), hi[2] + .05 - t, np.nan)
    return z, (lo, hi)


def geometry_proposal(height_m, bounds, config=None):
    """Local relief proposal, always unvalidated; does not infer OCR labels."""
    cfg = config or {}
    h=np.asarray(height_m,np.float32);valid=np.isfinite(h);empty=np.zeros(h.shape,bool)
    if valid.sum()<64:
        return dict(stroke=empty,roi=empty,exclusion=empty,residual=h.copy(),status='no_surface')
    lo,hi=np.asarray(bounds,float)
    dx=(hi[0]-lo[0])*1000/h.shape[1];dy=(hi[1]-lo[1])*1000/h.shape[0]
    if min(dx,dy)<=0:raise ValueError('Invalid reference bounds')
    radius=float(cfg.get('baseline_radius_mm',1.6))
    border=max(float(cfg.get('border_mm',3.5)),2*radius)
    threshold=float(cfg.get('relief_threshold_mm',.08))/1000
    if radius<=0 or threshold<=0:raise ValueError('Invalid proposal parameters')
    def ellipse(r):
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
            (2*max(1,int(np.ceil(r/dx)))+1,2*max(1,int(np.ceil(r/dy)))+1))
    filled=h.copy();filled[~valid]=float(np.median(h[valid]))
    baseline=cv2.morphologyEx(filled,cv2.MORPH_OPEN,ellipse(radius),borderType=cv2.BORDER_REPLICATE)
    residual=np.maximum(filled-baseline,0)
    residual[~valid]=np.nan
    # Explicit padded border also excludes the image boundary on a full rectangular mesh.
    dist=cv2.distanceTransform(np.pad(valid.astype(np.uint8),1),cv2.DIST_L2,5)[1:-1,1:-1]*min(dx,dy)
    interior=valid&(dist>border)
    raised=interior&(residual>threshold)
    line_mm=float(cfg.get('line_length_mm',35.))
    vl=cv2.morphologyEx(raised.astype(np.uint8),cv2.MORPH_OPEN,
        np.ones((max(3,int(np.ceil(line_mm/dy))),1),np.uint8))
    hl=cv2.morphologyEx(raised.astype(np.uint8),cv2.MORPH_OPEN,
        np.ones((1,max(3,int(np.ceil(line_mm/dx)))),np.uint8))
    lines=cv2.dilate(vl|hl,ellipse(.4)).astype(bool)
    exclusion=(valid&~interior)|lines
    stroke=raised&~exclusion
    n,labels,stats,_=cv2.connectedComponentsWithStats(stroke.astype(np.uint8),8)
    keep=np.zeros(n,bool)
    if n>1:keep[1:]=stats[1:,cv2.CC_STAT_AREA]>=max(2,int(np.ceil(.015/(dx*dy))))
    stroke=keep[labels]
    # Closing + physical dilation supplies background independently of individual strokes.
    closed=cv2.morphologyEx(stroke.astype(np.uint8),cv2.MORPH_CLOSE,ellipse(2.))
    roi=cv2.dilate(closed,ellipse(3.)).astype(bool)&interior&~exclusion
    fraction=float(stroke.sum()/max(1,interior.sum()))
    return dict(stroke=stroke,roi=roi,exclusion=exclusion,residual=residual,
        status='proposal_only' if stroke.any() else 'no_relief',threshold_m=threshold,
        floor_residual_m=None,plane_coefficients=None,method='local_opening_draft_v2',
        baseline_radius_mm=radius,border_mm=border,stroke_area_fraction=fraction,
        warning='review_required; threshold_not_calibrated_on_real_scan',
        assumptions='raised thin strokes relative to local floor; broad strokes, curved boards and damage require annotation review')


def proposal_from_saved_reference(reference_dir, config=None):
    """Preview proposal WITHOUT re-rendering or replacing reviewed annotation files."""
    ref=Path(reference_dir);data=np.load(ref/'board_reference.npz',allow_pickle=False)
    proposal=geometry_proposal(data['height_m'],data['bounds_m'],config)
    out=ref/'proposal_update_review';out.mkdir(exist_ok=True)
    for key in ('stroke','roi','exclusion'):
        save_png(out/(key+'.png'),proposal[key].astype(np.uint8)*255)
    np.savez_compressed(out/'proposal_maps.npz',**{k:proposal[k] for k in ('stroke','roi','exclusion','residual')})
    write_json(out/'proposal.json',{k:v for k,v in proposal.items() if k not in ('stroke','roi','exclusion','residual')})
    return proposal


def prepare_research_item(item, cfg, root, mi, scene, synthetic_masks=None):
    """Export annotation references and bind reviewed masks to the exact normalized mesh."""
    root = init_output(root)
    item['board_id'] = item['tag']
    item['mesh_id'] = item['tag']
    item['source_type'] = cfg.mesh_source
    item['board_identity_validated'] = False
    item['mesh_sha256'] = sha256(item['ply'])
    item['stroke_validated'] = False
    item['roi_validated'] = False
    item['text_validated'] = bool(synthetic_masks is not None)
    item['annotation_errors'] = []
    item['pose_review_status']='automatic_pose_not_manually_reviewed'
    if not item['plate']:
        item['pose_review_status']='nonplate_requires_review'
        item['stroke_source'] = 'missing_nonplate'
        return item
    h, bounds = board_height_grid(item, mi, scene)
    item['_reference_height_m'] = h
    proposal = geometry_proposal(h, bounds, getattr(cfg,'proposal_config',None))
    item['proposal_metadata']={k:v for k,v in proposal.items() if k not in ('stroke','roi','exclusion','residual')}
    item.update(proxy_stroke_uv=proposal['stroke'], proxy_roi_uv=proposal['roi'],
                exclusion_uv=proposal['exclusion'], stroke_source='geometry_proposal_unvalidated')
    ref = root / 'assets' / 'annotation_reference' / item['tag']
    ref.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(ref / 'board_reference.npz', height_m=h, residual_m=proposal['residual'],
                        proxy_stroke=proposal['stroke'], proxy_roi=proposal['roi'],
                        exclusion=proposal['exclusion'], bounds_m=np.asarray(bounds), M=item['M'])
    for key in ('stroke', 'roi', 'exclusion'):
        save_png(ref / ('proposal_' + key + '.png'), proposal[key].astype(np.uint8) * 255)
    finite = np.isfinite(h)
    view = np.zeros(h.shape, np.uint8)
    if finite.any():
        a, b = np.quantile(h[finite], [.01, .99])
        view[finite] = np.clip((h[finite] - a) / max(b-a, 1e-9) * 255, 0, 255).astype(np.uint8)
    save_png(ref / 'height_preview.png', view)
    metadata = dict(mesh_id=item['tag'], mesh_sha256=item['mesh_sha256'], shape_hw=list(h.shape),
                    bounds_m=np.asarray(bounds).tolist(), coordinate_frame='normalized_xy_uv',
                    pixel_convention='cell centers; row0=maxY, col0=minX', M_original_to_normalized=item['M'],
                    proposal={k:v for k,v in proposal.items() if k not in ('stroke','roi','exclusion','residual')})
    write_json(ref / 'reference.json', metadata)
    if synthetic_masks is not None:
        # These masks are generated alongside the glyphs, separate from frame/lines.
        item.update(stroke_mask_uv=synthetic_masks['stroke'], text_roi_uv=synthetic_masks['roi'],
                    exclusion_uv=synthetic_masks['exclusion'], stroke_validated=True,
                    roi_validated=True, stroke_source='synthetic_generator', annotation_version='synthetic_v1')
        # Generated UV masks describe the original mesh. Sample after inverse pose transform.
        item['mask_mapping'] = dict(frame='original_xy', bounds=synthetic_masks['bounds'],
                                    inverse_M=np.linalg.inv(item['M']))
        item['exclusion_mapping'] = item['mask_mapping']
        return item
    item['mask_mapping'] = dict(frame='normalized_xy', bounds=np.asarray(bounds))
    index_path = getattr(cfg, 'annotation_index_path', '')
    if not index_path:
        return item
    try:
        index_path = Path(index_path)
        index = json.loads(index_path.read_text(encoding='utf-8'))
        entry = index.get('boards', {}).get(item['tag'])
        if entry is None:
            return item
        if index.get('schema_version','woodblock.annotation.1.0') != 'woodblock.annotation.1.0':
            raise ValueError('Unsupported annotation schema_version')
        item['board_id'] = entry.get('board_id', item['tag'])
        item['board_identity_validated'] = bool(entry.get('board_identity_validated') and entry.get('reviewer'))
        item['annotation_version'] = entry.get('annotation_version', 'unversioned')
        if entry.get('coordinate_frame') != 'normalized_xy_uv':
            raise ValueError('Annotation masks require coordinate_frame=normalized_xy_uv')
        if entry.get('mesh_sha256') != item['mesh_sha256']:
            raise ValueError('Annotation mesh_sha256 differs from normalized mesh. Do not auto-resize/reuse masks.')
        if not np.allclose(np.asarray(entry.get('bounds_m')), np.asarray(bounds), atol=1e-7,rtol=0):
            raise ValueError('Annotation bounds_m mismatch')
        shape = tuple(entry['shape_hw'])
        paths = {k: (index_path.parent / entry[k]).resolve() for k in
                 ('stroke_mask_path', 'text_roi_mask_path', 'exclusion_mask_path') if entry.get(k)}
        if 'exclusion_mask_path' not in paths:
            raise ValueError('Explicit exclusion mask is required, including an all-zero mask if appropriate')
        # Annotation masks may use a different grid size from the proposal, but not from each other.
        exclusion = read_mask(paths['exclusion_mask_path'], shape)
        item['exclusion_uv'] = exclusion
        if 'text_roi_mask_path' in paths:
            item['text_roi_uv'] = read_mask(paths['text_roi_mask_path'], shape)
            item['roi_validated'] = bool(entry.get('roi_validated', False) and entry.get('reviewer'))
        elif any(not c.get('pseudo') for c in item.get('chars',[])):
            item['roi_validated'] = bool(entry.get('roi_validated',False) and entry.get('reviewer'))
        if 'stroke_mask_path' in paths:
            item['stroke_mask_uv'] = read_mask(paths['stroke_mask_path'], shape)
            item['stroke_source'] = 'annotation_uv'
            item['stroke_validated'] = bool(entry.get('stroke_validated', False) and entry.get('reviewer'))
        item['text_validated'] = bool(entry.get('text_validated', False) and entry.get('reviewer'))
        if item['stroke_validated'] and not item['stroke_mask_uv'].any():
            raise ValueError('Reviewed stroke mask is empty')
        if item['roi_validated'] and 'text_roi_uv' in item and not item['text_roi_uv'].any():
            raise ValueError('Reviewed ROI is empty')
        if item['stroke_validated'] and item['roi_validated'] and 'text_roi_uv' in item:
            outside=item['stroke_mask_uv'] & ~exclusion & ~item['text_roi_uv']
            if outside.any():raise ValueError('Reviewed ROI does not contain reviewed strokes')
        item['annotation_provenance'] = {**entry,'resolved_mask_hashes':{k:sha256(p) for k,p in paths.items()}}
        if entry.get('labels_path'):
            lp=(index_path.parent/entry['labels_path']).resolve()
            item['annotation_provenance']['labels_sha256']=sha256(lp)
    except Exception as exc:
        # Reject all partially loaded annotations, keep diagnostic proposal only.
        item['board_identity_validated']=False
        item.pop('stroke_mask_uv', None)
        item.pop('text_roi_uv', None)
        item.update(stroke_validated=False, roi_validated=False, text_validated=False,
                    exclusion_uv=proposal['exclusion'], stroke_source='geometry_proposal_unvalidated')
        item['annotation_errors'].append(str(exc))
    return item


def attach_visibility_points(item, max_points=10000):
    h=item.get('_reference_height_m')
    if h is None or not item.get('stroke_validated') or item.get('stroke_mask_uv') is None:
        return item
    lo,hi=np.asarray(item['mesh'].bounds)
    yy,xx=np.nonzero(np.isfinite(h))
    points=np.column_stack([lo[0]+(xx+.5)/h.shape[1]*(hi[0]-lo[0]),
                            hi[1]-(yy+.5)/h.shape[0]*(hi[1]-lo[1]),h[yy,xx]])
    mapping=item.get('mask_mapping',dict(frame='normalized_xy',bounds=np.asarray(item['mesh'].bounds)))
    keep=sample_uv(item['stroke_mask_uv'],points,mapping)
    keep &= ~sample_uv(item.get('exclusion_uv'),points,item.get('exclusion_mapping',mapping))
    points=points[keep]
    if len(points)>max_points:points=points[np.linspace(0,len(points)-1,max_points).astype(int)]
    item['_stroke_visibility_points']=points
    return item


def observed_stroke_fraction(item,cam,mi,scene):
    points=item.get('_stroke_visibility_points')
    method='uniform_normalized_XY_stroke_surface_samples; first object hit; tolerance=0.2mm'
    if points is None or len(points)==0:
        return dict(value=None,status='missing_validated_stroke_surface_samples',method=method,n_samples=0)
    R,t=np.asarray(cam['R']),np.asarray(cam['t'])
    camera=points@R.T+t
    xy=camera@np.asarray(cam['K']).T
    uv=xy[:,:2]/np.maximum(camera[:,2,None],1e-12)
    inside=(camera[:,2]>0)&(uv[:,0]>=0)&(uv[:,0]<cam['W'])&(uv[:,1]>=0)&(uv[:,1]<cam['H'])
    origin=np.asarray(cam['origin']);delta=points-origin
    distance=np.linalg.norm(delta,axis=1);directions=delta/np.maximum(distance[:,None],1e-12)
    ray=mi.Ray3f(mi.Point3f(*[np.full(len(points),origin[k]) for k in range(3)]),
                 mi.Vector3f(*[directions[:,k].copy() for k in range(3)]))
    hit=np.asarray(scene.ray_intersect(ray).t).reshape(-1)
    visible=inside & np.isfinite(hit) & (np.abs(hit-distance)<=.0002)
    return dict(value=float(visible.mean()),status='estimated_xy_area_fraction',method=method,
                n_samples=len(points),n_visible=int(visible.sum()))


def sample_uv(mask, points, mapping):
    if mask is None:
        return np.zeros(len(points), bool)
    points = np.asarray(points)
    if mapping.get('frame') == 'original_xy':
        M = np.asarray(mapping['inverse_M'])
        points = points @ M[:3,:3].T + M[:3,3]
    lo, hi = np.asarray(mapping['bounds'], float)
    u = (points[:,0] - lo[0]) / (hi[0]-lo[0])
    v = (hi[1] - points[:,1]) / (hi[1]-lo[1])
    inside = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
    cols = np.clip(np.floor(u * mask.shape[1]).astype(int), 0, mask.shape[1]-1)
    rows = np.clip(np.floor(v * mask.shape[0]).astype(int), 0, mask.shape[0]-1)
    return inside & np.asarray(mask, bool)[rows, cols]


def project_geometry(item, cam, mi, scene, chars_px=None, chunk=131072):
    H, W = int(cam['H']), int(cam['W'])
    R, t = np.asarray(cam['R']), np.asarray(cam['t'])
    invK = np.linalg.inv(np.asarray(cam['K']))
    maps = {k: np.zeros((H,W), bool) for k in
            ('valid','surface_valid','stroke','text_roi','exclusion','proxy_stroke','proxy_roi')}
    maps.update(depth_z_m=np.full((H,W), np.nan, np.float32),
                normal_world=np.full((H,W,3), np.nan, np.float32),
                position_world_m=np.full((H,W,3), np.nan, np.float32))
    default_mapping = dict(frame='normalized_xy', bounds=np.asarray(item['mesh'].bounds))
    mapping = item.get('mask_mapping', default_mapping)
    sources = {'stroke': item.get('stroke_mask_uv', item.get('proxy_stroke_uv')),
               'text_roi': item.get('text_roi_uv'), 'exclusion':item.get('exclusion_uv'),
               'proxy_stroke':item.get('proxy_stroke_uv'), 'proxy_roi':item.get('proxy_roi_uv')}
    for start in range(0, H*W, chunk):
        ids = np.arange(start, min(start+chunk, H*W))
        xy = np.column_stack([ids % W + .5, ids // W + .5, np.ones(len(ids))])
        directions = (xy @ invK.T) @ R
        directions /= np.linalg.norm(directions, axis=1, keepdims=True)
        ray = mi.Ray3f(mi.Point3f(*[np.full(len(ids), cam['origin'][k]) for k in range(3)]),
                       mi.Vector3f(*[directions[:,k].copy() for k in range(3)]))
        si = scene.ray_intersect(ray)
        hit = np.asarray(si.is_valid()).reshape(-1).astype(bool)
        good = ids[hit]
        points = np.column_stack([np.asarray(si.p[k]).reshape(-1) for k in range(3)])[hit]
        normals = np.column_stack([np.asarray(si.n[k]).reshape(-1) for k in range(3)])[hit]
        maps['valid'].ravel()[good] = True
        top = normals[:,2] > .05 if item.get('plate') else np.ones(len(good),bool)
        maps['surface_valid'].ravel()[good] = top
        maps['position_world_m'].reshape(-1,3)[good] = points
        maps['normal_world'].reshape(-1,3)[good] = normals
        maps['depth_z_m'].ravel()[good] = (points @ R.T+t)[:,2]
        for key, source in sources.items():
            mp = default_mapping if key.startswith('proxy_') else (
                item.get('exclusion_mapping', mapping) if key == 'exclusion' else mapping)
            maps[key].ravel()[good] = sample_uv(source, points, mp) & top
    # Reviewed character polygons can provide the ROI without a separate UV ROI.
    if not maps['text_roi'].any() and item.get('roi_validated'):
        roi = np.zeros((H,W),np.uint8)
        for c in chars_px or []:
            if c.get('visible') and not c.get('pseudo') and c.get('poly_px'):
                cv2.fillPoly(roi,[np.round(np.asarray(c['poly_px'])-.5).astype(np.int32)],1)
        maps['text_roi'] = roi.astype(bool) & maps['surface_valid']
    for key in ('stroke','text_roi','proxy_stroke','proxy_roi'):
        maps[key] &= ~maps['exclusion']
    return maps


def _result(value=None, status='ok', **extra):
    return dict(value=value, status=status, **extra)


def compute_metrics(rgb, maps, provenance, config=None):
    """A replaceable, fully specified reference, inspired by the draft HTML.

    sRGB gray -> Gaussian -> Sobel (scale 1/8) and Laplacian (ksize=3).
    2D and 3D use the same ROI, edge dilation and background distance rule.
    Background = pixels farther from source edges; it may include glyph interiors.
    """
    t0 = time.perf_counter()
    c = config or MetricConfig()
    if c.sigma_px <= 0 or c.eps <= 0 or c.min_pixels < 1:
        raise ValueError('Invalid metric configuration')
    if min(c.band_radius_px,c.background_gap_px,c.support_margin_px,c.f1_tolerance_px) < 0:
        raise ValueError('Negative morphology radius')
    if not (0 <= c.canny_low_quantile < c.canny_high_quantile <= 1):
        raise ValueError('Canny quantiles must be ordered within [0,1]')
    a = np.asarray(rgb)
    if a.dtype != np.uint8 or a.ndim != 3 or a.shape[2] != 3:
        raise ValueError('Expected RGB uint8')
    if any(np.asarray(maps[k]).shape != a.shape[:2] for k in
           ('valid','surface_valid','stroke','text_roi','exclusion','proxy_stroke','proxy_roi')):
        raise ValueError('Image and mask shapes differ')
    gray = (a.astype(np.float32)/255) @ np.array([.2126,.7152,.0722],np.float32)
    smooth = cv2.GaussianBlur(gray,(0,0),c.sigma_px)
    gx = cv2.Sobel(smooth,cv2.CV_32F,1,0,ksize=3,scale=1/8)
    gy = cv2.Sobel(smooth,cv2.CV_32F,0,1,ksize=3,scale=1/8)
    gradient = np.hypot(gx,gy)
    lap = cv2.Laplacian(smooth,cv2.CV_32F,ksize=1)
    margin = c.support_margin_px
    object_support = morph(maps['valid'],margin,'erode')
    roi_ok = bool(provenance.get('roi_validated') and maps['text_roi'].any())
    stroke_ok = bool(provenance.get('stroke_validated') and maps['stroke'].any())
    support = object_support & maps['surface_valid'] & maps['text_roi'] & ~maps['exclusion'] if roi_ok else np.zeros(gray.shape,bool)
    proxy_support = object_support & maps['surface_valid'] & maps['proxy_roi'] & ~maps['exclusion']
    active_support = support if roi_ok else proxy_support
    stroke = maps['stroke'] if stroke_ok else maps['proxy_stroke']
    raw_3d = stroke & ~morph(stroke,1,'erode')
    edge3d = morph(raw_3d,c.band_radius_px) & active_support
    bg3d = active_support & ~morph(raw_3d,c.band_radius_px+c.background_gap_px)
    values = {'lap_global': _result(status='insufficient_support'),
              'lap_local': _result(status='no_validated_roi'),
              'ec_2d': _result(status='no_validated_roi'),
              'E_net': _result(status='missing_validated_stroke_or_roi'),
              'E_proxy': _result(status='no_proxy_support'),
              'edge_f1': _result(status='missing_validated_stroke_or_roi')}
    preprocess_s=time.perf_counter()-t0
    tlap=time.perf_counter()
    if object_support.sum() >= c.min_pixels:
        values['lap_global'] = _result(float(lap[object_support].var()))
    values['lap_global']['timing_s']=time.perf_counter()-tlap
    tlap=time.perf_counter()
    if roi_ok and support.sum() >= c.min_pixels:
        values['lap_local'] = _result(float(lap[support].var()))
    elif roi_ok:
        values['lap_local'] = _result(status='insufficient_support')
    values['lap_local']['timing_s']=time.perf_counter()-tlap
    def ratio(edge,bg):
        tratio=time.perf_counter()
        if edge.sum()<c.min_pixels or bg.sum()<c.min_pixels:
            return _result(status='insufficient_edge_or_background',edge_pixels=int(edge.sum()),background_pixels=int(bg.sum()),timing_s=time.perf_counter()-tratio)
        ge,gb = float(np.median(gradient[edge])),float(np.median(gradient[bg]))
        value = ge/max(gb,c.eps)
        return _result(value, 'den_floor' if gb<c.eps else 'ok', edge_gradient=ge,
                       background_gradient=gb,edge_pixels=int(edge.sum()),background_pixels=int(bg.sum()),timing_s=time.perf_counter()-tratio)
    candidate=ratio(edge3d,bg3d)
    if stroke_ok and roi_ok:
        values['E_net']=candidate
    else:
        values['E_proxy']=candidate
        if values['E_proxy']['status']=='ok':values['E_proxy']['status']='proxy_only'
    canny=np.zeros(gray.shape,bool)
    edge2d=np.zeros(gray.shape,bool);bg2d=edge2d.copy()
    if roi_ok and support.sum()>=c.min_pixels:
        t2d=time.perf_counter()
        g=gradient[support]
        low,high=np.quantile(g,[c.canny_low_quantile,c.canny_high_quantile])*255*8
        low,high=max(1.,float(low)),max(2.,float(high))
        high=max(high,low+1)
        canny=cv2.Canny(np.clip(smooth*255,0,255).astype(np.uint8),low,high,L2gradient=True)>0
        canny &= support
        edge2d=morph(canny,c.band_radius_px)&support
        bg2d=support&~morph(canny,c.band_radius_px+c.background_gap_px)
        values['ec_2d']=ratio(edge2d,bg2d)
        values['ec_2d'].update(canny_low=low,canny_high=high)
        values['ec_2d']['timing_s']=time.perf_counter()-t2d
        if stroke_ok:
            tf1=time.perf_counter()
            a2=canny&support;b3=raw_3d&support
            if a2.sum()>=c.min_pixels and b3.sum()>=c.min_pixels:
                precision=float((a2&morph(b3,c.f1_tolerance_px)).sum()/a2.sum())
                recall=float((b3&morph(a2,c.f1_tolerance_px)).sum()/b3.sum())
                values['edge_f1']=_result(2*precision*recall/max(precision+recall,1e-12),precision=precision,recall=recall)
            else:values['edge_f1']=_result(status='few_edges')
            values['edge_f1']['timing_s']=time.perf_counter()-tf1
    # ec_3d is the paper-facing name; E_net is a compatibility alias, not an extra independent metric.
    values['ec_3d']=dict(values['E_net'])
    values['ec_3d_proxy']=dict(values['E_proxy'])
    reason=None
    if not provenance.get('stroke_validated'):reason='stroke_not_validated'
    elif not roi_ok:reason='missing_validated_text_roi'
    elif values['E_net']['status']!='ok':reason=values['E_net']['status']
    if provenance.get('geometry_error'):
        values={k:_result(status='geometry_error') for k in values}
        reason='geometry_error'
    valid_pixels=int(maps['valid'].sum())
    info=dict(metric_version=METRIC_VERSION,metric_config=asdict(c),metrics=values,
              metric_spec=dict(status='draft_reference_not_official_son_code',luma='BT709_on_encoded_RGB',laplacian='4_neighbors',
                  band='dilate raw edge by band_radius_px',background='shared ROI minus dilated raw edge; may include stroke interiors',
                  ec_3d_alias='E_net',pdf='Son draft 2026-11-05; unspecified Canny/tolerance choices explicit in config'),
              ec_3d=values['ec_3d']['value'] if values['ec_3d']['status']=='ok' else None,
              ec_3d_lower_bound=values['ec_3d']['value'] if values['ec_3d']['status']=='den_floor' else None,
              E_net=values['E_net']['value'] if values['E_net']['status']=='ok' else None,
              E_net_lower_bound=values['E_net']['value'] if values['E_net']['status']=='den_floor' else None,
              E_proxy=values['E_proxy']['value'],E_status=values['E_net']['status'],
              eligible_main_analysis=reason is None,invalid_reason=reason,object_fallback=False,
              measurement_scope='text_roi' if roi_ok else 'proxy_roi_diagnostic',
              support_pixels=int(active_support.sum()),edge_pixels=int(edge3d.sum()),
              background_pixels=int(bg3d.sum()),stroke_pixels=int(maps['stroke'].sum()),
              valid_pixels=valid_pixels,text_roi_pixels=int(maps['text_roi'].sum()),
              text_roi_visible_pixels=int((maps['text_roi']&maps['surface_valid']).sum()),
              observed_text_fraction=provenance.get('stroke_visibility',{}).get('value'),
              observed_text_fraction_status=provenance.get('stroke_visibility',{}).get('status','not_available'),
              stroke_fraction_of_object=float(maps['stroke'].sum()/max(1,valid_pixels)),
              edge_gradient=candidate.get('edge_gradient'),background_gradient=candidate.get('background_gradient'),
              timing_s=time.perf_counter()-t0,shared_preprocessing_s=preprocess_s,
              timing_scope='wall clock; 2D includes Canny/regions; E aggregation excludes shared 3D geometry/regions; see total and geometry_time_s')
    regions=dict(support=active_support,stroke_edge=edge3d,background=bg3d,
                 edge_2d=edge2d,background_2d=bg2d,raw_edge_2d=canny,raw_edge_3d=raw_3d)
    return info,regions,gradient


def run_external_backend(path, context):
    """Plugin API v1: compute_metrics(context) -> {version, metrics:{name:{value,status}}}."""
    if not path:
        return dict(status='not_configured',metrics={})
    t0=time.perf_counter()
    try:
        spec=importlib.util.spec_from_file_location('woodblock_metric_plugin',path)
        if spec is None or spec.loader is None:
            raise ImportError('Cannot load metric backend: '+str(path))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        # Read-only views prevent an accidental plugin edit from changing exported evidence.
        import copy
        safe=copy.deepcopy({k:v for k,v in context.items() if k not in ('rgb','maps')})
        if 'rgb' in context:
            safe['rgb']=np.array(context['rgb'],copy=True);safe['rgb'].flags.writeable=False
        if 'maps' in context:
            safe['maps']={k:np.array(v,copy=True) for k,v in context['maps'].items()}
            for v in safe['maps'].values():v.flags.writeable=False
        result=module.compute_metrics(safe)
        if not isinstance(result,dict) or not result.get('version') or not isinstance(result.get('metrics'),dict):
            raise ValueError('Backend must return version and metrics dictionary')
        for key,value in result['metrics'].items():
            if not isinstance(value,dict) or 'status' not in value or 'value' not in value:
                raise ValueError('Missing value/status for metric '+key)
            v=value['value']
            if v is not None and (not np.isscalar(v) or not np.isfinite(float(v))):
                raise ValueError('Invalid scalar for metric '+key)
        return {**result,'status':'ok','backend_sha256':sha256(path),'timing_s':time.perf_counter()-t0}
    except Exception as exc:
        return dict(status='error',error=str(exc),metrics={})


def save_png(path, array):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not cv2.imwrite(str(path),array):raise IOError('Cannot write '+str(path))


def metric_failure(rgb, maps, provenance, config, error):
    """Keep renderer output when a metric implementation fails; never invent scores."""
    shape=rgb.shape[:2];empty=np.zeros(shape,bool)
    values={name:_result(status='error:'+type(error).__name__) for name in METRIC_REGISTRY}
    info=dict(metric_version=METRIC_VERSION,metric_config=asdict(config or MetricConfig()),metrics=values,
        ec_3d=None,ec_3d_lower_bound=None,E_net=None,E_net_lower_bound=None,E_proxy=None,
        E_status='metric_error',eligible_main_analysis=False,invalid_reason='metric_error',object_fallback=False,
        measurement_scope='unavailable_metric_error',metric_error=str(error),gradient_status='unavailable_metric_error',
        support_pixels=0,edge_pixels=0,background_pixels=0,stroke_pixels=int(maps['stroke'].sum()),
        valid_pixels=int(maps['valid'].sum()),text_roi_pixels=int(maps['text_roi'].sum()),text_roi_visible_pixels=0,
        observed_text_fraction=None,observed_text_fraction_status='not_measured',edge_gradient=None,background_gradient=None,
        timing_s=0.,shared_preprocessing_s=0.,timing_scope='metric_failed')
    regions={k:empty.copy() for k in ('support','stroke_edge','background','edge_2d','background_2d','raw_edge_2d','raw_edge_3d')}
    return info,regions,np.zeros(shape,np.float32)


def export_sample(root,name,render_rgb,final_rgb,maps,provenance,config=None,backend_path=''):
    root=init_output(root)
    write_json(root/'metric_contract.json',dict(metric_version=METRIC_VERSION,config=asdict(config or MetricConfig()),registry=METRIC_REGISTRY,approval_status='draft_pending_supervisor_feedback'))
    if render_rgb.shape!=final_rgb.shape:raise ValueError('Stage image shape mismatch')
    provenance={**provenance,'sample_id':name}
    record={**provenance,'schema_version':SCHEMA_VERSION,'pipeline_version':PIPELINE_VERSION,
            'sample_id':name,'metric_config':asdict(config or MetricConfig()),'files':{}}
    stage_results={}
    for stage,rgb in [('render',render_rgb),('final',final_rgb)]:
        try:
            result,regions,gradient=compute_metrics(rgb,maps,provenance,config)
        except Exception as exc:
            result,regions,gradient=metric_failure(rgb,maps,provenance,config,exc)
        external=run_external_backend(backend_path,dict(api_version=2,rgb=rgb,maps=maps,regions=regions,
                  gradient=gradient,reference_metrics=result['metrics'],
                  provenance=provenance,stage=stage,config=asdict(config or MetricConfig())))
        result['external_backend']=external
        stage_results[stage]=result
        suffix='' if stage=='final' else '_render'
        # 16-bit fixed-scale visualization; raw float32 maps remain in NPZ.
        grad_path=f'edge_maps/{name}{suffix}_gradient.png'
        save_png(root/grad_path,np.clip(gradient*65535,0,65535).astype(np.uint16))
        record['files'][stage+'_gradient']=grad_path
        if stage=='final':
            sample=gradient[maps['valid']]
            vmax=float(np.quantile(sample,.99)) if sample.size else 1.
            preview_path=f'edge_maps/{name}_gradient_preview.png'
            save_png(root/preview_path,np.clip(gradient/max(vmax,1e-9)*255,0,255).astype(np.uint8))
            record['files']['gradient_preview']=preview_path
            record['gradient_preview_scale_p99']=vmax
        if stage=='final':
            out_maps={**maps,**regions,'gradient_final':gradient}
            final_regions=regions
        else:
            render_gradient=gradient
    out_maps['gradient_render']=render_gradient
    geom_path=f'geometry/{name}_maps.npz'
    np.savez_compressed(root/geom_path,**out_maps)
    record['files']['geometry']=geom_path
    for key,mask in {**{k:maps[k] for k in ['stroke','text_roi','valid','surface_valid','exclusion','proxy_stroke','proxy_roi']},
                     **final_regions}.items():
        path=f'masks/{name}_{key}.png';save_png(root/path,mask.astype(np.uint8)*255)
        record['files'][key]=path
    overlay=final_rgb.copy()
    for mask,color in [(final_regions['stroke_edge'],[255,0,0]),(final_regions['background'],[0,255,0])]:
        overlay[mask]=(.45*overlay[mask]+.55*np.asarray(color)).astype(np.uint8)
    path=f'overlays/{name}_metric_overlay.png'
    save_png(root/path,cv2.cvtColor(overlay,cv2.COLOR_RGB2BGR));record['files']['metric_overlay']=path
    # Four labeled panels at full native resolution: observed image, stroke, ROI/exclusion, measured regions.
    H,W=final_rgb.shape[:2]
    stroke_img=np.repeat((maps['stroke']*255).astype(np.uint8)[...,None],3,axis=2)
    roi_img=np.zeros_like(final_rgb);roi_img[maps['proxy_roi']]=[180,120,0];roi_img[maps['text_roi']]=[0,180,255];roi_img[maps['exclusion']]=[255,0,255]
    panels=[]
    for label,im in [('FINAL RGB',final_rgb),('STROKE '+provenance.get('stroke_source','missing'),stroke_img),
                     ('REVIEWED ROI cyan / PROXY amber / EXCLUSION magenta',roi_img),('EDGE red / CONTROL green',overlay)]:
        im=im.copy();cv2.rectangle(im,(0,0),(W,28),(0,0,0),-1)
        cv2.putText(im,label,(8,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1,cv2.LINE_AA);panels.append(im)
    diag=np.vstack([np.hstack(panels[:2]),np.hstack(panels[2:])])
    path=f'overlays/{name}_diagnostic.png';save_png(root/path,cv2.cvtColor(diag,cv2.COLOR_RGB2BGR));record['files']['diagnostic']=path
    path=f'render_images/{name}.png';save_png(root/path,cv2.cvtColor(render_rgb,cv2.COLOR_RGB2BGR));record['files']['render_image']=path
    record['files']['image']=f'images/{name}.jpg'
    valid=maps['valid'];gray=(final_rgb.astype(np.float32)/255)@np.array([.2126,.7152,.0722],np.float32)
    border=np.zeros(valid.shape,bool);border[[0,-1],:]=True;border[:,[0,-1]]=True
    record['image_qa']=dict(blown_fraction=float((gray[valid]>=254/255).mean()) if valid.any() else None,
                            dark_fraction=float((gray[valid]<=3/255).mean()) if valid.any() else None,
                            object_touches_image_border=bool((border&valid).any()),
                            geometry_status='ok' if valid.any() else 'no_surface',
                            definition='BT709 encoded luma; blown>=254/255, dark<=3/255; object only')
    record['stages']=stage_results
    record.update({k:v for k,v in stage_results['final'].items() if k not in ['external_backend','metrics']})
    record['files']['metric_log']=f'logs/{name}_metric.json'
    write_json(root/record['files']['metric_log'],record)
    return record


def summarize_run(root,run_metadata=None):
    """Rebuild deterministic wide/long exports from per-sample logs, including invalid rows."""
    root=Path(root);logs=[json.loads(p.read_text()) for p in sorted((root/'logs').glob('*_metric.json'))]
    wide=[];long=[]
    for r in logs:
        for stage,s in r['stages'].items():
            row={k:r.get(k) for k in ('run_id','sample_id','board_id','mesh_id','seed','pair_id','assigned_condition',
                    'observed_quality','stroke_source','stroke_validated','roi_validated','annotation_version')}
            row.update(stage=stage,metric_version=s['metric_version'],E_net=s['E_net'],E_proxy=s['E_proxy'],
                       pipeline_version=r.get('pipeline_version'),schema_version=r.get('schema_version'),
                       CER=None,ocr_status='pending',
                       E_status=s['E_status'],invalid_reason=s['invalid_reason'],eligible_main_analysis=s['eligible_main_analysis'],
                       object_fallback=False,measurement_scope=s['measurement_scope'],support_pixels=s['support_pixels'],
                       edge_pixels=s['edge_pixels'],background_pixels=s['background_pixels'],
                       observed_text_fraction=s['observed_text_fraction'],observed_text_fraction_status=s['observed_text_fraction_status'],
                       edge_gradient=s['edge_gradient'],background_gradient=s['background_gradient'],
                       metric_time_s=s['timing_s'],image=r['files'].get('image'),maps=r['files'].get('geometry'))
            row.update({k:r.get('metric_config',{}).get(k) for k in asdict(MetricConfig())})
            for name,m in s['metrics'].items():
                row[name]=m['value'];row[name+'_status']=m['status']
                # E_net remains null for den_floor in wide table; lower bound has its own column.
                if name=='E_net':row[name]=s['E_net'];row['E_net_lower_bound']=s['E_net_lower_bound']
                if name=='ec_3d':row[name]=s.get('ec_3d');row['ec_3d_lower_bound']=s.get('ec_3d_lower_bound')
                long.append({**{k:row[k] for k in ('run_id','sample_id','board_id','stage','metric_version')},
                             'metric':name,'value':m['value'],'status':m['status'],
                             'metric_compute_time_s':m.get('timing_s'),
                             'eligible_main_analysis':bool(m['status']=='ok' and name in ('lap_global','lap_local','ec_2d','ec_3d'))})
            external=s.get('external_backend',{})
            row['external_backend_status']=external.get('status')
            for name,m in external.get('metrics',{}).items():
                row['external__'+name]=m['value'];row['external__'+name+'_status']=m['status']
            row['sampling_px_per_mm']=r.get('sampling_px_per_mm',{}).get('median')
            row['board_identity_validated']=r.get('board_identity_validated',False)
            for name,m in external.get('metrics',{}).items():
                long.append(dict(run_id=r.get('run_id'),sample_id=r['sample_id'],board_id=r.get('board_id'),stage=stage,
                    metric_version=external.get('version'),metric='external__'+name,value=m['value'],status=m['status'],
                    eligible_main_analysis=False,backend_sha256=external.get('backend_sha256')))
            wide.append(row)
    write_csv(root/'render_metrics.csv',wide)
    write_csv(root/'metrics_long.csv',long)
    # Hashes and low-resolution distances measure duplicates, not perceptual realism.
    fingerprints={};duplicate=[];small=[]
    for r in logs:
        if not r['files'].get('image'):continue
        path=root/r['files']['image']
        if not path.exists():continue
        digest=sha256(path)
        if digest in fingerprints:duplicate.append([fingerprints[digest],r['sample_id']])
        fingerprints[digest]=r['sample_id']
        im=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if im is not None:small.append((r['sample_id'],r['board_id'],cv2.resize(im,(48,36)).astype(float)/255))
    nearest={}
    for sid,bid,a in small:
        ds=[(float(np.mean(np.abs(a-b))),sj) for sj,bj,b in small if bj==bid and sj!=sid]
        nearest[sid]=dict(zip(('distance','sample_id'),min(ds))) if ds else None
    conditions={};statuses={}
    for r in logs:
        k=r.get('assigned_condition','unknown');conditions[k]=conditions.get(k,0)+1
        k=r['E_status'];statuses[k]=statuses.get(k,0)+1
    def balance(counts):
        v=np.asarray(list(counts.values()),float)
        if len(v)<2:return None
        p=v[v>0]/v.sum();return float(-(p*np.log(p)).sum()/np.log(len(v)))
    rows_final=[r for r in wide if r['stage']=='final']
    # Missing conditions are reported explicitly against the six planned groups.
    for p in ('clean','normal','hard'):
        for level in ('sharp','soft'):conditions.setdefault(p+'_'+level,0)
    summary=dict(schema_version=SCHEMA_VERSION,pipeline_version=PIPELINE_VERSION,metric_version=METRIC_VERSION,
                 n_samples=len(logs),n_measured=sum(bool(r['files'].get('geometry')) for r in logs),
                 n_metric_rows=len(wide),condition_counts=conditions,E_status_counts=statuses,
                 n_valid_E_net=sum(r['eligible_main_analysis'] for r in rows_final),
                 exact_duplicates=duplicate,nearest_same_board=nearest,condition_balance=balance(conditions),
                 missing_conditions=[k for k,v in conditions.items() if v==0],
                 limitations=['Draft metrics; no claim of realism or OCR effectiveness without independent evaluation.',
                              'Proxy masks are not text ground truth.',
                              'Repeated renders of one board are not independent boards.'],
                 run_metadata=run_metadata or {})
    # Descriptive statistics, not a substitute for board-aware inference or CER validation.
    grouped={}
    for r in logs:
        for stage,s in r['stages'].items():
            for name,metric in s['metrics'].items():
                if metric['value'] is None:continue
                key='|'.join(str(x) for x in [r.get('board_id'),r.get('assigned_condition'),stage,name,metric['status']])
                grouped.setdefault(key,[]).append(float(metric['value']))
    summary['metric_distributions']={k:dict(n=len(v),p5=float(np.quantile(v,.05)),median=float(np.median(v)),
                                          p95=float(np.quantile(v,.95))) for k,v in grouped.items()}
    parameters={}
    for group,names in [('camera',('tilt_deg','fov_deg','distance_m')),('lights',('key_elev_deg','fill_ratio')),
                        ('effects',('defocus_sigma_px','jpeg_quality'))]:
        for name in names:
            v=[float(r[group][name]) for r in logs if r.get(group,{}).get(name) is not None]
            if v:
                counts,edges=np.histogram(v,bins=10)
                parameters[group+'.'+name]=dict(n=len(v),min=min(v),max=max(v),median=float(np.median(v)),
                                                histogram_counts=counts.tolist(),histogram_edges=edges.tolist(),
                                                scope='observed range only; not planned parameter coverage')
    summary['parameter_distributions']=parameters
    summary['dataset_audit']=dataset_audit(root,(run_metadata or {}).get('planned_parameter_ranges',{}))
    write_json(root/'summary.json',summary)
    return summary


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(clean_json(rows))


def export_rejection(root,rec):
    stage=dict(metric_version=METRIC_VERSION,E_net=None,E_net_lower_bound=None,E_proxy=None,E_status='render_rejected',
               invalid_reason='render_rejected',eligible_main_analysis=False,measurement_scope='not_measured',
               support_pixels=0,edge_pixels=0,background_pixels=0,observed_text_fraction=None,
               observed_text_fraction_status='not_measured',edge_gradient=None,background_gradient=None,timing_s=0,
               metrics={k:_result(status='not_measured') for k in ('lap_global','lap_local','ec_2d','ec_3d','E_net','E_proxy','ec_3d_proxy','edge_f1')})
    record={**rec,'schema_version':SCHEMA_VERSION,'pipeline_version':PIPELINE_VERSION,'files':{},
            'stroke_validated':False,'roi_validated':False,'stroke_source':'not_measured','object_fallback':False,
            'E_status':'render_rejected','stages':{'render':stage,'final':stage}}
    write_json(Path(root)/'logs'/(rec['sample_id']+'_metric.json'),record)
    return record


def recompute_run(root,config=None,backend_path=''):
    """Recompute on SAVED images/maps. Use a copy of a run to preserve previous measurements."""
    root=Path(root)
    for p in sorted((root/'logs').glob('*_metric.json')):
        r=json.loads(p.read_text())
        if not r['files'].get('geometry'):continue
        m=dict(np.load(root/r['files']['geometry'],allow_pickle=False))
        a=cv2.imread(str(root/r['files']['image']));b=cv2.imread(str(root/r['files']['render_image']))
        if a is None or b is None:raise ValueError('Missing stage image for '+r['sample_id'])
        provenance={k:v for k,v in r.items() if k not in ('files','stages','metrics','schema_version','pipeline_version',
                     'sample_id','metric_config','image_qa','gradient_preview_scale_p99') and k not in r['stages']['final']}
        # Identity/provenance fields are retained even when also present in result dictionaries.
        for k in ('run_id','board_id','mesh_id','seed','assigned_condition','stroke_source','stroke_validated','roi_validated'):
            provenance[k]=r.get(k)
        export_sample(root,r['sample_id'],cv2.cvtColor(b,cv2.COLOR_BGR2RGB),cv2.cvtColor(a,cv2.COLOR_BGR2RGB),m,
                      provenance,config,backend_path)
    return summarize_run(root)


def join_ocr(root,ocr_csv):
    """Attach collaborator-supplied CER, never run OCR or infer missing CER.

    Input must be one row per full image with run_id,sample_id,CER,ocr_model,
    ocr_version,gt_version. Patch CER needs aggregation by the OCR owner first.
    """
    root=Path(root)
    with open(ocr_csv,encoding='utf-8-sig') as f:ocr=list(csv.DictReader(f))
    lookup={}
    for row in ocr:
        required=('run_id','sample_id','CER','ocr_model','ocr_version','gt_version')
        if any(not row.get(k) for k in required):raise ValueError('Missing OCR identity/config/GT fields')
        key=(row['run_id'],row['sample_id'])
        if key in lookup:raise ValueError('Duplicate OCR sample '+str(key))
        cer=float(row['CER'])
        if not np.isfinite(cer) or cer<0:raise ValueError('CER must be finite and >=0 (can exceed 1)')
        lookup[key]=row
    with open(root/'render_metrics.csv',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    final=[r for r in rows if r['stage']=='final']
    valid_keys={(r['run_id'],r['sample_id']) for r in final}
    unknown=set(lookup)-valid_keys
    if unknown:raise ValueError('OCR samples absent from run: '+str(sorted(unknown)))
    for r in final:
        row=lookup.get((r['run_id'],r['sample_id']))
        r.update({k:(row.get(k) if row else None) for k in ('CER','ocr_model','ocr_version','gt_version')})
        r['ocr_status']='received' if row else 'pending'
    write_csv(root/'metric_cer_join.csv',final)
    return dict(matched=len(lookup),pending=len(final)-len(lookup))




def _get_nested(record,path):
    value=record
    for key in path.split('.'):
        if not isinstance(value,dict):return None
        value=value.get(key)
    return value


def dataset_audit(root, planned_ranges=None):
    """Son draft dataset diagnostics; flags are not automatic sample rejection."""
    root=Path(root);planned_ranges=planned_ranges or {}
    logs=[json.loads(p.read_text()) for p in sorted((root/'logs').glob('*_metric.json'))]
    for rec in logs:
        label_path=root/'labels'/(rec['sample_id']+'.json')
        if label_path.exists():
            try:
                label=json.loads(label_path.read_text())
                rec.setdefault('background',label.get('background'))
            except (OSError,ValueError):pass
    descriptors=[];rows=[];hashes={};flags={};unreadable=[]
    for rec in logs:
        sid=rec['sample_id'];row=dict(sample_id=sid,board_id=rec.get('board_id'),flags=[])
        rel=rec.get('files',{}).get('image')
        if not rel:
            row.update(status='not_rendered');rows.append(row);continue
        path=root/rel;im=cv2.imread(str(path))
        if im is None:
            row['flags'].append('unreadable');unreadable.append(sid)
        else:
            digest=sha256(path)
            if digest in hashes:row['flags'].append('exact_dup');row['exact_duplicate_of']=hashes[digest]
            else:hashes[digest]=sid
            # BT.709 luma on encoded RGB, matching the image metric stage.
            rgb=cv2.cvtColor(im,cv2.COLOR_BGR2RGB).astype(np.float32)/255
            gray=rgb@np.array([.2126,.7152,.0722],np.float32)
            small=cv2.resize(gray,(48,36),interpolation=cv2.INTER_AREA).ravel().astype(float)
            small-=small.mean();norm=np.linalg.norm(small)
            if norm<1e-12:row['descriptor_status']='constant_image'
            else:descriptors.append((sid,rec.get('board_id'),small/norm))
            qa=rec.get('image_qa',{})
            if qa.get('blown_fraction') is not None and qa['blown_fraction']>.02:row['flags'].append('blown')
            if qa.get('dark_fraction') is not None and qa['dark_fraction']>.05:row['flags'].append('too_dark')
            if qa.get('object_touches_image_border'):row['flags'].append('plate_cut')
        rows.append(row)
    byid={r['sample_id']:r for r in rows}
    for sid,bid,a in descriptors:
        others=[(float(np.clip(1-np.dot(a,b),0,2)),sj) for sj,bj,b in descriptors if bj==bid and sj!=sid]
        if others:
            distance,other=min(others);byid[sid].update(d_NN=distance,nearest_same_board=other)
            if distance<.002:byid[sid]['flags'].append('near_dup')
        else:byid[sid]['d_NN']=None
    for row in rows:
        row['qa_flagged']=bool(row['flags'])
        for flag in row['flags']:flags[flag]=flags.get(flag,0)+1
        row['flags']='|'.join(row['flags'])
    def entropy(field,expected=None):
        counts={str(k):0 for k in (expected or [])}
        for rec in logs:
            if not rec.get('files',{}).get('image'):continue
            k=str(_get_nested(rec,field) or 'unknown');counts[k]=counts.get(k,0)+1
        v=np.asarray(list(counts.values()),float);K=len(v)
        if v.sum()==0 or K<2:return dict(value=None,status='fewer_than_two_categories',counts=counts)
        p=v[v>0]/v.sum()
        return dict(value=float(-(p*np.log(p)).sum()/np.log(K)),status='ok',counts=counts)
    parameters={}
    paths=['camera.tilt_deg','camera.fov_deg','lights.key_elev_deg','lights.fill_ratio','effects.defocus_sigma_px','effects.jpeg_quality']
    for path in paths:
        vals=[float(_get_nested(r,path)) for r in logs if r.get('files',{}).get('image') and _get_nested(r,path) is not None]
        if not vals:continue
        bounds=planned_ranges.get(path)
        if bounds is not None:
            lo,hi=map(float,bounds);scope='planned_range'
        else:lo,hi=min(vals),max(vals);scope='observed_range_only'
        if hi<=lo:
            parameters[path]=dict(C=None,status='constant_range',n=len(vals),scope=scope);continue
        hist,edges=np.histogram(vals,bins=10,range=(lo,hi))
        parameters[path]=dict(C=float(np.count_nonzero(hist)/10),scope=scope,counts=hist.tolist(),edges=edges.tolist(),
            outside_range=sum(x<lo or x>hi for x in vals))
    # Descriptive rank correlation only; renders of one board are repeated measures.
    correlations=[];binned=[]
    for path in paths:
        for metric in ('ec_3d','lap_global','lap_local','ec_2d'):
            for board in sorted({r.get('board_id','unknown') for r in logs}):
                pairs=[]
                for rec in logs:
                    if rec.get('board_id')!=board:continue
                    x=_get_nested(rec,path);m=rec.get('stages',{}).get('final',{}).get('metrics',{}).get(metric,{})
                    if x is not None and m.get('status')=='ok' and m.get('value') is not None:
                        pairs.append((float(x),float(m['value'])))
                if len(pairs)<3:continue
                x,y=np.asarray(pairs).T
                def ranks(v):
                    _,inv,counts=np.unique(v,return_inverse=True,return_counts=True)
                    start=np.cumsum(counts)-counts
                    return (start+(counts-1)/2)[inv]
                rx,ry=ranks(x),ranks(y)
                rho=float(np.corrcoef(rx,ry)[0,1]) if np.std(rx)>0 and np.std(ry)>0 else None
                correlations.append(dict(board_id=board,parameter=path,metric=metric,n=len(x),spearman=rho,
                    scope='descriptive_within_board_no_p_value_or_causal_claim'))
                if max(x)>min(x):
                    edges=np.linspace(min(x),max(x),7);indices=np.minimum(np.searchsorted(edges,x,side='right')-1,5)
                    for b in range(6):
                        yy=y[indices==b]
                        binned.append(dict(board_id=board,parameter=path,metric=metric,bin=b,lo=edges[b],hi=edges[b+1],
                            n=len(yy),p5=float(np.quantile(yy,.05)) if len(yy) else None,
                            median=float(np.median(yy)) if len(yy) else None,p95=float(np.quantile(yy,.95)) if len(yy) else None))
    weak=[]
    for rec in logs:
        m=rec.get('stages',{}).get('final',{}).get('metrics',{}).get('ec_3d',{})
        if m.get('status')=='ok' and m.get('value') is not None:weak.append((m['value'],rec['sample_id']))
    weak=sorted(weak)[:int(np.ceil(.05*len(weak)))]
    audit=dict(version='son_pdf_20261105_draft_adapter_1',n_images=sum(bool(r.get('files',{}).get('image')) for r in logs),
        flag_counts=flags,flags_policy='report_only; near duplicates may be intentional controlled pairs',
        entropy={p:entropy(p) for p in ('board_id','background','camera_device')},
        parameter_coverage=parameters,within_board_correlations=correlations,
        weakest_ec_3d=[dict(sample_id=s,value=v) for v,s in weak],
        limitations=['d_NN is centered cosine distance at 48x36; not perceptual realism',
                     'C over observed range does not measure planned coverage',
                     'No CER, deltaCER, KID/FID/C2ST inferred or computed without required external data'])
    write_csv(root/'dataset_qa.csv',rows);write_csv(root/'parameter_metric_bins.csv',binned)
    write_json(root/'dataset_audit.json',audit)
    return audit


def sampling_density(maps):
    p=np.asarray(maps['position_world_m']);valid=maps['surface_valid']
    values=[];directions=[]
    for axis in (0,1):
        if axis==0:delta=p[1:]-p[:-1];ok=valid[1:]&valid[:-1]
        else:delta=p[:,1:]-p[:,:-1];ok=valid[:,1:]&valid[:,:-1]
        d=np.linalg.norm(delta,axis=2)*1000
        d=d[ok&np.isfinite(d)&(d>1e-8)]
        density=1/d
        if density.size:values.extend(density[::max(1,len(density)//20000)].tolist())
        directions.append(float(np.median(density)) if density.size else None)
    return dict(median=float(np.median(values)) if values else None,axis_medians=directions,
        status='estimated_from_visible_surface_neighbors' if values else 'unavailable',
        method='inverse adjacent world-surface distance; not automatic scale normalization')

# Notebook adapter. External backend cannot overwrite reference E_net or validation gates.
METRIC_CONFIG = MetricConfig()

def sample_signature(item, cfg, profile_settings):
    annotations=item.get('annotation_provenance',{})
    config_state={k:v for k,v in asdict(cfg).items() if k not in ('output_root','resume_run_id')}
    state={"config":config_state,"profile":profile_settings,"mesh":item.get('mesh_sha256'),
           "notebook_source_sha256":NOTEBOOK_SOURCE_SHA256,"metrics_patch_sha256":METRICS_PATCH_SHA256,
           "annotation":annotations,"chars":item.get("chars",[]),"proposal":item.get("proposal_metadata"),"metric":asdict(METRIC_CONFIG),"version":PIPELINE_VERSION,
           "controlled":getattr(cfg,'controlled_conditions',[])}
    state['mask_hashes']={k:hashlib.sha256(np.asarray(item[k]).tobytes()).hexdigest()
                          for k in ('stroke_mask_uv','text_roi_uv','exclusion_uv') if k in item}
    state['textures']={p:sha256(p) for p in getattr(cfg,'texture_paths',[])}
    if cfg.metric_backend_path:state['backend_sha256']=sha256(cfg.metric_backend_path)
    return hashlib.sha256(json.dumps(clean_json(state),sort_keys=True).encode()).hexdigest()

def benchmark_render_metrics(final_rgb, item, cam, chars_px, root, name, render_rgb=None, sample_metadata=None):
    geometry_t0=time.perf_counter()
    geometry_error=None
    try:
        maps=project_geometry(item,cam,mi,occlusion_scene(item['ply']),chars_px)
    except Exception as exc:
        geometry_error=type(exc).__name__+': '+str(exc)
        H,W=final_rgb.shape[:2]
        maps={k:np.zeros((H,W),bool) for k in ('valid','surface_valid','stroke','text_roi','exclusion','proxy_stroke','proxy_roi')}
        maps.update(depth_z_m=np.full((H,W),np.nan,np.float32),normal_world=np.full((H,W,3),np.nan,np.float32),
                    position_world_m=np.full((H,W,3),np.nan,np.float32))
    geometry_s=time.perf_counter()-geometry_t0
    source_metadata={k:item.get(k) for k in ('board_id','mesh_id','source_type','mesh_sha256','stroke_source',
                         'stroke_validated','roi_validated','text_validated','annotation_version','annotation_errors',
                         'annotation_provenance','source_mesh_path','pose_info','proposal_metadata','board_identity_validated','pose_review_status')}
    source_metadata.update(run_id=RUN_ID,geometry_occlusion_scope='first_hit_on_object_only',
                           M_original_to_normalized=item['M'],**(sample_metadata or {}))
    source_metadata['normalized_bounds_m']=np.asarray(item['mesh'].bounds).tolist()
    source_metadata['geometry_time_s']=geometry_s
    source_metadata['notebook_source_sha256']=NOTEBOOK_SOURCE_SHA256
    source_metadata['metrics_patch_sha256']=METRICS_PATCH_SHA256
    source_metadata['geometry_error']=geometry_error
    source_metadata['sampling_px_per_mm']=sampling_density(maps)
    try:source_metadata['stroke_visibility']=observed_stroke_fraction(item,cam,mi,occlusion_scene(item['ply'])) if not geometry_error else {}
    except Exception as exc:source_metadata['stroke_visibility']={'value':None,'status':'visibility_error','error':str(exc)}
    # Whole-character fraction is measurable for real labeled polygons, not for empty pseudo grids.
    nonpseudo=[c for c in chars_px if not c.get('pseudo')]
    source_metadata['visible_character_fraction']=sum(bool(c.get('visible')) for c in nonpseudo)/len(nonpseudo) if nonpseudo else None
    record=export_sample(root,name,render_rgb if render_rgb is not None else final_rgb,final_rgb,maps,
                         source_metadata,METRIC_CONFIG,cfg.metric_backend_path)
    print("Metric:",name,record['measurement_scope'],record['E_status'],flush=True)
    return clean_json({k:v for k,v in record.items() if k not in ('stages',)})

# Controlled mode: each entry overrides declared parameters; unspecified ranges stay stochastic.
def experiment_assignment(item_tag,i,n):
    if cfg.experiment_mode=='profiles':
        p=get_data_profile(item_tag,i,n);level=get_detail_level(item_tag,i,n)
        return p,level,p+'_'+level,None
    if cfg.experiment_mode!='controlled' or not cfg.controlled_conditions:
        raise ValueError("controlled mode needs controlled_conditions; see examples")
    entry=cfg.controlled_conditions[i%len(cfg.controlled_conditions)]
    return entry.get('profile','clean'),entry.get('detail_level','sharp'),entry['condition_id'],entry

_sample_camera_base=sample_camera
_sample_lights_base=sample_lights
_get_profile_config_base=get_profile_config
_ACTIVE_CONDITION=None

def get_profile_config(profile,detail_level='sharp'):
    c=_get_profile_config_base(profile,detail_level)
    if _ACTIVE_CONDITION:
        for group in ('camera_geometry','lighting','camera_effects'):
            c[group]={**c[group],**_ACTIVE_CONDITION.get(group,{})}
        if 'exposure_target' in _ACTIVE_CONDITION:c['exposure_target']=_ACTIVE_CONDITION['exposure_target']
    return c

def sample_camera(mesh,rng,W,H,plate_like,data_profile='normal',detail_level='sharp'):
    return _sample_camera_base(mesh,rng,W,H,plate_like,data_profile,detail_level)

print("Research output contract:",PIPELINE_VERSION,"| metrics:",METRIC_VERSION)
