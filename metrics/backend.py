"""API adapter for the independent measure() implementation; scores stay external."""
from pathlib import Path
import importlib.util


def compute_metrics(context):
    path = Path(__file__).with_name("metrics.py")
    spec = importlib.util.spec_from_file_location("woodblock_comparison_metrics", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    maps = context["maps"]
    provenance = context["provenance"]
    reviewed = bool(provenance.get("stroke_validated") and provenance.get("roi_validated"))
    result = module.measure(context["rgb"], maps["stroke"], maps["valid"], roi=maps["text_roi"])
    metrics = {}
    for key in ("E_net", "edge_gradient", "background_gradient", "laplacian_var", "tenengrad"):
        value = result.get(key)
        name = "E_proxy" if key == "E_net" and not reviewed else key
        status = result.get("status", "unavailable") if value is not None else "unavailable"
        if key == "E_net" and value is not None and not reviewed:
            status = "proxy_unvalidated"
        metrics[name] = {"value": value, "status": status}
    return {"version": "woodblock_measure_adapter_1.0", "metrics": metrics}
