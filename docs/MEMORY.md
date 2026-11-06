# Local memory planning and dynamic notebook exports

Section 3b now routes binary STL files above one million triangles through clustering before QEM, uses configurable 100,000-face chunks, releases the area sample earlier, and estimates memory before key merging, accumulator allocation, face merging and native simplification. QEM uses a single explicitly centered float64 input instead of two Python-side temporary vertex arrays. Remaining native allocation failures are reported with actionable guidance.

In section 1, the defaults are:

```python
cfg.memory_budget_gb = 5.5
cfg.preprocess_chunk_faces = 100_000
```

The budget is in GiB and estimates notebook/child process RSS plus extra allocations. It is a conservative planning guard, not an OS-enforced cap. It cannot guarantee total system RAM below 6 GB, cannot predict all native-library allocations, and does not control subsequent rendering allocations. If 6 GB includes Windows and VS Code, use a smaller pipeline budget, for example 3.5 GiB, subject to other applications' usage.

Restart the kernel after a MemoryError to release old mesh arrays. Update the checkout, then run configuration and cells in order. Lowering final target_faces alone does not bound simplifier input memory. When a planning guard stops execution, do not simply raise the budget on a constrained laptop. Preprocess the scan on a machine with enough RAM, or deliberately choose a different voxel/target configuration and repeat geometry validation. The pipeline does not automatically coarsen the scan, bypass failed geometry checks or assert research equivalence.

For a small local render pilot, deliberately set width=1024, height=768, spp_cpu=4, ink_max_side=2048 and replace the existing cfg.n_images override with 1. These settings change render/texture conditions and must be recorded. They do not guarantee that preprocessing a large scan fits into memory. Keep the real experiment settings when comparing research metrics.

Section 12.5 still executes the versioned metrics update in notebook globals. It now binds the exported names referenced by later cells explicitly, including experiment_assignment, PIPELINE_VERSION and sample_signature, so static analysis sees their definitions. A missing export fails at the loader rather than later in rendering. Yellow diagnostics alone are not runtime failures; run the loader before section 13.

Validation performed in this change: notebook code-cell syntax and whitespace checks. The real source scan, Windows RAM peak, native simplification and LLVM/CUDA rendering have not been exercised in this environment. This change reduces avoidable allocation and rejects risky jobs; it is not a claim that the full original scan can be processed under 6 GB.
