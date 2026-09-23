---
name: gl-utils-reference
description: Code-accurate technical reference for gl_utils.py, a pixel-native 2D ModernGL rendering helper built on Pygame and NumPy. Use when writing rendering loops, defining object structures, or managing memory buffers and collisions.
---

# `gl_utils` Reference

`gl_utils.py` is a pixel-native 2D rendering helper built on Pygame, ModernGL, and NumPy. It translates standard Python data structures into hardware-accelerated GPU instances while preserving your local tracking sequences in native Pygame pixel space.

---

## Data Layout Specifications

Every record tracking structure in your game code must be a mutable sequence matching these exact data lengths and field alignments. 

### 1. Rectangle (`"rect"`)
* **Length:** 10 elements.
* **Layout:** `[x, y, r, g, b, a, thickness, width, height, rotation]`
* **Behavior:** `thickness = 0.0` draws a filled rectangle. Values up to `0.5` create increasingly thick inner borders.

### 2. Point (`"point"`)
* **Length:** 7 elements.
* **Layout:** `[x, y, r, g, b, a, size]`
* **Behavior:** `size` dictates diameter in pixels. Requires running `ctx.enable(moderngl.PROGRAM_POINT_SIZE)` before drawing.

### 3. Textured Rectangle (`"tex"`)
* **Length:** 12 elements.
* **Layout:** `[x, y, r, g, b, a, thickness, width, height, rotation, tile_x, tile_y]`
* **Behavior:** Index `6` maps directly to `in_thickness` in the vertex buffer configuration. Use white `(255, 255, 255)` for the RGB components to preserve native texture colors without tinting.

---

## Buffer Lifecycle & Core Pipelines

### Global State Context
The helper uses internal global variables `WIDTH` and `HEIGHT` (defaulting to 800x600) to compute aspect ratios. Update these using:
```python
WIDTH, HEIGHT = set_viewport_size(width, height)
```
*Note: Passing dimensions less than or equal to `0` raises a `ValueError`.*

### Memory Allocation
Allocate fixed arrays before starting your game loop to establish clear stride boundaries:
* **Rect Stride:** 40 bytes per record (`4 * 10` floats).
* **Point Stride:** 28 bytes per record (`4 * 7` floats).
* **Tex Stride:** 48 bytes per record (`4 * 12` floats).

```python
# Create empty float32 tracking arrays
rect_instances, point_instances, tex_instances = get_new_instances(rn, pn, tn)
```

### Initial Packing Pipeline
Before compiling your ModernGL vertex arrays, your data lists must be initialized and normalized:
```python
# Normalizes color coordinates down to 0.0-1.0 and converts rotation degrees to radians
rects, rect_instances = to_gl(rects, rect_instances, "rect")
```

---

## Mutation API Reference

All mutation helper functions modify your primary Python tracking lists **in place** and return the updated sequence object directly. 

| Function Signature | In-Place Target Effects |
| :--- | :--- |
| `modify_xy(idx, data, x, y)` | Overwrites indices `0` and `1` with center coordinates. |
| `modify_rgba(idx, data, r, g, b, a)` | Replaces indices `[2:6]` with integer values from `0` to `255`. |
| `modify_size(idx, data, width, height, type_)` | For `"rect"`/`"tex"`, updates `7,8`. For `"point"`, updates size at `6`. |
| `modify_scale(idx, data, sx, sy, type_)` | Compatibility alias pointing directly to `modify_size`. |
| `modify_rot(idx, data, angle, type_='rect')` | For `"rect"`/`"tex"`, sets rotation degrees at index `9`. |
| `modify_thickness(idx, data, factor, type_='rect')` | For `"rect"`, overwrites thickness tuning at index `6`. |
| `modify_texture(idx, data, tilex, tiley, type_='tex')` | For `"tex"`, maps asset atlas cell grid offsets to `10,11`. |

### The Three-Step Sync Rule
To display local updates on the GPU, always follow this explicit three-step pipeline:
```python
modify_xy(0, sprites, 500, 300)                                       # 1. Mutate Python list
tex_instances = update_instances(0, sprites, tex_instances)           # 2. Re-pack specific slice
tex_vbo.write(tex_instances[0].tobytes(), offset=0 * 48)              # 3. Stream byte stride to GPU
```

---

## Line & Polygon Pipelines

### Vector Buffers
Line tracking requires raw pixel coordinate sequences and single color arrays. They run as independent, non-instanced draw routines:
```python
line_vao, line_vbo = build_line_obj(ctx, line_program, points, (255, 255, 255, 255))
```
* **Buffer Rewriting:** `update_line_obj(vbo, points, rgba)` updates data paths without rebuilding structural objects. If replacement structures contain more vertices than the original buffer size, it raises a `ValueError`.

### Convex Fills and Caching
When triggering `render_polygon(vao, points, fill=True)`, the engine cross-references an internal `lru_cache(maxsize=256)`. 
* **Validation:** The engine builds a structural relative coordinate footprint to verify if the geometry is simple, non-degenerate, and convex.
* **Execution:** If valid, it renders using `moderngl.TRIANGLE_FAN`. If it detects self-intersections or concave bends, it falls back automatically to an outline loop using `moderngl.LINE_LOOP`.

---

## Physics & Interaction Interface

All collision operations execute using standard Python math inside local system memory. **No GPU readbacks are required**.

* **Bounding Boxes:** `check_collision(player, obstacles, 'rect')` checks for intersections between rotated rectangles using the Separating Axis Theorem (SAT). Returns tracking markers formatted as `('rt', index)`.
* **Point Collisions:** `check_collision(player, points, 'point')` runs point-in-rotated-rect calculations. Returns markers formatted as `('p', index)`.
* **Mouse Interactions:** `check_mouse_collisions(mx, my, data, type_)` isolates user input selections. Points use a simple un-rotated bounding box check based on their `size` attribute. Rectangles and textures run full oriented geometric collision checks. Returns matching index positions directly.
* **Convex Geometries:** `check_convex_polygon_collision(poly1, poly2)` and `check_convex_polygon_rect_collision(polygon, rect)` provide pure vector intersection detection via SAT. Non-convex or self-intersecting shapes raise a `ValueError`.

---

## Hardware Shader Layout Requirements

Your vertex shaders must implement these exact attribute names and component order to match the data mapping expected by `ctx.vertex_array`:

### `build_rect_objs` Attribute Layout
* `quad_vbo` (VBO data format: `'2f 2f'`): `quad_position`, `quad_uv`
* `ivbo` (Instance data format: `'2f 4f 1f 2f 1f /i'`): `in_offset`, `in_color`, `in_thickness`, `in_size`, `in_rotation`

### `build_tex_objs` Attribute Layout
* `quad_vbo` (VBO data format: `'2f 2f'`): `quad_position`, `quad_uv`
* `ivbo` (Instance data format: `'2f 4f 1f 2f 1f 2f /i'`): `in_offset`, `in_color`, `in_thickness`, `in_size`, `in_rotation`, `in_tile`

### `build_point_objs` Attribute Layout
* `ivbo` (Instance data format: `'2f 4f 1f /i'`): `in_offset`, `in_color`, `in_size`

### `build_line_obj` / `build_polygon_obj` Attribute Layout
* `vbo` (Buffer data format: `'2f 4f'`): `in_position`, `in_color`

*Note: Every vertex program requires the matching uniform declaration: `uniform vec2 u_viewport_size;`*

---

## Texture Loading Protocols
`load_texture(ctx, path)` processes assets automatically using Pygame's exporter:
```python
texture = load_texture(ctx, "assets/sprite.png")
```
* **Axis Conversions:** The pipeline uses `pygame.image.tobytes(surface, 'RGBA', True)`. The trailing `True` argument instructs Pygame to automatically perform a vertical flip to match OpenGL's bottom-left texture coordinates.
* **Filtering Rule:** Textures are strictly bound to `NEAREST` filtering for both magnification and minification to keep pixel-art edge profiles sharp.

## Further clarifications
Take a look at `gl_utils.py` for better understanding of the specifications mentioned.
