---
name: png-bitmap-generator
description: Create or modify deterministic pixel-art PNG assets in a marked PyGameKit project using bitmap JSON and png_generator.py. Use for project sprites, atlases, textures, and other generated PNG artwork.
---

# PNG Bitmap Generator

Use this workflow when the user asks to create a PNG with the project's JSON
bitmap generator. This produces deterministic pixel art; do not substitute an
image-generation model.

## Immediate Bootstrap and Workspace Boundary

Before gathering requirements or creating an asset, run this from the toolkit
root:

```bash
python3 bootstrap.py
```

Available bootstrap modes:
- `python3 bootstrap.py` – discover the active project directory or create `New Project/`
- `python3 bootstrap.py --new` – create a new project directory (interactive prompt)
- `python3 bootstrap.py --scan` – list all existing marked project directories
- `python3 bootstrap.py --exists <name>` – check if a project directory exists

The shared generator remains at `png_generator.py` in the toolkit root. All
project-specific PNG work belongs in the workspace path printed by bootstrap,
referred to below as `<project-root>`:

* editable specifications: `<project-root>/bitmap/`
* generated images and asset metadata: `<project-root>/assets/`

Do not create project `bitmap/` or `assets/` directories at the toolkit root.

## Gather the request

If the user has not described the asset, ask what they want generated. Also ask
for any missing information that cannot be safely inferred:

- pixel dimensions as `width x height`
- output filename
- desired subject, colors, and style

Ask for the missing details together in one concise question. Do not ask again
for details already supplied. Use a lowercase kebab-case filename ending in
`.png` when the user leaves naming to you.

## Create the bitmap

Work from the toolkit root containing `png_generator.py`. Bootstrap, rather than
the asset task, is responsible for creating the project directories.

Write the model-authored specification to:

```text
<project-root>/bitmap/<asset-name>.json
```

Use this schema:

```json
{
  "dim": [16, 16],
  "fill": [
    {"coord": [7, 1], "color": [1.0, 0.0, 0.0, 1.0]},
    {"coords": [[6, 2], [7, 2], [8, 2]], "color": [0.8, 0.8, 0.9, 1.0]},
    {"from": [5, 3], "to": [9, 7], "color": [0.2, 0.6, 1.0, 1.0]}
  ]
}
```

Rules:

- `dim` is `[width, height]`; the generated PNG has those exact dimensions.
- Coordinates use a top-left origin. X increases rightward and Y downward.
- Colors are OpenGL-style RGB or RGBA components in the inclusive `0.0–1.0`
  range. RGB values default to alpha `1.0`.
- Omit transparent pixels. The generator makes every unfilled pixel transparent.
- Group pixels of the same color with `coords` instead of repeating entries.
- Use inclusive `from`/`to` rectangles for solid rectangular regions.
- Later fill entries overwrite earlier entries, which is useful for details on
  top of large regions.
- Keep the design legible at its requested native size and leave transparent
  padding when the asset will rotate or animate.

The `fill` field also accepts a compact coordinate map when that is clearer:

```json
{
  "dim": "3x2",
  "fill": {
    "0,0": [1.0, 0.0, 0.0, 1.0],
    "1,0": [0.0, 1.0, 0.0, 1.0]
  }
}
```

## Generate and verify

Run:

```bash
python3 png_generator.py --bitmap "<project-root>/bitmap/<asset-name>.json" --output "<project-root>/assets/<asset-name>.png"
```

Do not overwrite an existing JSON or PNG unless the user requested replacement.
Otherwise choose a versioned name such as `<asset-name>-v2`.

Confirm that the command succeeds, inspect the resulting PNG, and verify its
dimensions, transparency, orientation, silhouette, and requested colors. If it
is incorrect, edit the JSON and rerun the same command. Keep the final bitmap
JSON as the editable source.

After asset work is complete, run `python3 bootstrap.py` again to refresh the
`.pygamekit-project` inventory.

Report both final project paths to the user:

```text
<project-root>/bitmap/<asset-name>.json
<project-root>/assets/<asset-name>.png
```