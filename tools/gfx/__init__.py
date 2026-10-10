"""English replacement graphics: library, targets and build integration.

Design and notes: docs/workstreams/gfx-pipeline.md.

Library
    font.py      pixel fonts (assets/font/*.txt)
    textart.py   text to styled bitmaps (outline, bold, colours, boxes)
    image.py     indexed bitmaps, text-art images, PNG import/preview
    tiles.py     8x8 cells, 2bpp tiles, tile banks, plane map entries

Build integration
    target.py    the interface of a target: Context (what build(ctx) gets) and Result
    romio.py     RomPatch: in-place writes with owners, declared ranges and clash checks
    build.py     the target registry, the graphics sub-regions and the two graphics
                 phases of tools/patch/build.py (python -m tools.gfx.build lists them)
    apply.py     python -m tools.gfx.apply IN OUT [--target NAME]: targets on a ROM copy,
                 without the full build

Targets (one module each, build(ctx) -> Result; registered in build.py)
    labels.py, intro.py, cards.py, title.py

Analysis
    vram.py      harness --vram dumps: render layers, compare with ROM data, VBlank queue
    harness.py   run the harness, poke save states, diff screenshots, contact sheets
    inventory.py survey of the game's graphics loaders

Tests: every test_*.py, run by python -m tools.gfx.test_all [rom/baserom.ngc].
"""
