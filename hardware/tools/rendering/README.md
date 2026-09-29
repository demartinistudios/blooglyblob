# Current rendering

Install `requirements.txt` into a local virtual environment. Dependencies were exercised with Python 3.12; the lock records exact installed versions. Do not commit the environment.

```sh
python hardware/tools/rendering/run.py --view r22/part-GS11 --font /path/to/licensed/font.ttf --output hardware/.work/rendering/new-run
```

Use `--view eye-details` for the five eye-interface illustrations. Other scene keys are in `hardware/rendering/scenes/views.json`. The runner resolves all inputs through `hardware/rendering/source-lock.json`,
checks the selected CAD identity and native/export bindings, and requires a new
output directory. Roles select current meshes, native mesh evidence, assembly,
joints, palette and scenes without relying on historical payload folders.
Scene dimensions must be explicitly reviewed for the selected CAD identity. It renders the current composed meshes directly. Cameras, palette, occurrence transforms and cm→mm conversion are retained. Each run records package versions and the supplied font's hash; the original illustration font was macOS Arial. Supply a legally available matching font for exact typography, or review the visual differences. No font is redistributed here.

A new native geometry export must update the current composed mesh and its provenance deliberately. Inspect bounds, volume, joints, appearance and visibility; keep unchanged rows exact. Review generated images before promoting them into guide source. Original CAD inspection screenshots remain immutable evidence and are not synthetically recreated by this renderer.
