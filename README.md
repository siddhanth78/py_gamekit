# `gl_utils`

`gl_utils.py` is a pixel-native 2D rendering helper built on pygame, ModernGL,
and NumPy. It supports:

- Instanced rectangles, points, and textured rectangles
- RGBA colors and alpha blending
- Lines, polylines, and polygon outlines
- Filled convex polygons
- Rectangle, point, mouse, and convex-polygon collision checks
- Partial GPU-buffer updates

Public object data stays in pygame units: pixel coordinates and dimensions,
0-255 RGBA values, and rotation in degrees. The module creates the GPU-ready
copies without changing the source records.

## Requirements

- Python 3
- OpenGL 3.3 or newer
- `pygame`
- `moderngl`
- `numpy`

```bash
python3 -m pip install pygame moderngl numpy
```

Keep the supplied shaders next to the module:

```text
gl_utils.py
shaders/
├── line.vert
├── line.frag
├── point.vert
├── point.frag
├── rect.vert
├── rect.frag
├── tex.vert
└── tex.frag
```

## Complete minimal program

This program opens a window and draws one rectangle and one point:

```python
import moderngl
import pygame

from gl_utils import (
    build_point_objs,
    build_rect_objs,
    get_new_instances,
    load_program,
    set_viewport_size,
    to_gl,
)


pygame.init()
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(
    pygame.GL_CONTEXT_PROFILE_MASK,
    pygame.GL_CONTEXT_PROFILE_CORE,
)
pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

screen = pygame.display.set_mode(
    (800, 600),
    pygame.OPENGL | pygame.DOUBLEBUF,
)
viewport_size = set_viewport_size(*screen.get_size())

ctx = moderngl.create_context()
ctx.viewport = (0, 0, *viewport_size)
ctx.enable(moderngl.PROGRAM_POINT_SIZE)
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

rect_program = load_program(ctx, "shaders/rect.vert", "shaders/rect.frag")
point_program = load_program(ctx, "shaders/point.vert", "shaders/point.frag")

rect_program["u_viewport_size"] = viewport_size
point_program["u_viewport_size"] = viewport_size

# [x, y, r, g, b, a, thickness, width, height, rotation_degrees]
rects = [[400, 300, 255, 80, 80, 200, 0.0, 120, 60, 20]]

# [x, y, r, g, b, a, size]
points = [[400, 300, 255, 255, 255, 255, 20]]

rect_instances, point_instances, unused_tex_instances = get_new_instances(
    100, 100, 0
)
rects, rect_instances = to_gl(rects, rect_instances, "rect")
points, point_instances = to_gl(points, point_instances, "point")

rect_vao, rect_vbo = build_rect_objs(ctx, rect_program, rect_instances)
point_vao, point_vbo = build_point_objs(ctx, point_program, point_instances)

clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    ctx.clear(0.0, 0.0, 0.0)
    rect_vao.render(moderngl.TRIANGLES, instances=len(rects))
    point_vao.render(moderngl.POINTS, vertices=1, instances=len(points))
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

## Coordinate and value conventions

| Value | Convention |
| --- | --- |
| Position | Pixels, with the origin at the top left and positive Y downward |
| Rectangle/texture dimensions | Pixels |
| Point size | Pixels |
| RGBA | 0-255 |
| Rotation | Degrees |
| Thickness | Normalized quad-UV value |
| Atlas tile | Zero-based column and row |

`to_gl()` and `update_instances()` pack source records into NumPy arrays. They
normalize RGBA and convert rectangle/texture rotation to radians only in the GPU
copy. Source lists remain in the conventions above.

## Window and viewport size

Call `set_viewport_size()` after creating the pygame window:

```python
viewport_size = set_viewport_size(*screen.get_size())
ctx.viewport = (0, 0, *viewport_size)
```

Every supplied vertex shader requires the same viewport tuple:

```python
rect_program["u_viewport_size"] = viewport_size
point_program["u_viewport_size"] = viewport_size
tex_program["u_viewport_size"] = viewport_size
line_program["u_viewport_size"] = viewport_size
```

Objects retain their pixel dimensions at different resolutions. A rectangle
whose width is `60` remains 60 pixels wide at both 800×600 and 1200×800.

For a runtime resize, update the module, OpenGL viewport, and active programs:

```python
viewport_size = set_viewport_size(*screen.get_size())
ctx.viewport = (0, 0, *viewport_size)

for program in (rect_program, point_program, tex_program, line_program):
    program["u_viewport_size"] = viewport_size
```

Existing object and line buffers do not need rebuilding because their positions
and dimensions remain in pixels.

## Object record layouts

Field order is part of the API. Records must be mutable sequences with the exact
number of values shown below.

### Rectangle

```text
[x, y, r, g, b, a, thickness, width, height, rotation]
```

```python
rect = [200, 150, 255, 0, 0, 128, 0.08, 100, 50, 45]
```

- `x`, `y` are the center.
- `width`, `height` are pixel dimensions.
- `rotation` is in degrees about the center.
- `thickness=0` draws a filled rectangle.
- Values between `0` and `0.5` draw increasingly thick borders.
- Values around `0.5` or greater cover essentially the entire rectangle.

### Point

```text
[x, y, r, g, b, a, size]
```

```python
point = [100, 100, 255, 255, 255, 255, 20]
```

`size` is the point width and height in pixels. Enable
`moderngl.PROGRAM_POINT_SIZE` before rendering points.

### Textured rectangle

```text
[x, y, r, g, b, a, unused, width, height, rotation, tile_x, tile_y]
```

```python
sprite = [320, 240, 255, 255, 255, 200, 0, 64, 64, 0, 2, 1]
```

The seventh field is unused by the supplied texture shader. RGB tints the
texture, and instance alpha multiplies texture alpha. Use white
`(255, 255, 255)` to preserve the original texture colors.

## Instance storage and GPU objects

Allocate fixed-capacity NumPy arrays:

```python
rect_instances, point_instances, tex_instances = get_new_instances(
    rect_capacity,
    point_capacity,
    texture_capacity,
)
```

| Type | Array shape | Stride | Bytes per record |
| --- | --- | --- | ---: |
| Rectangle | `(rect_capacity, 10)` | `rstride` | 40 |
| Point | `(point_capacity, 7)` | `pstride` | 28 |
| Texture | `(texture_capacity, 12)` | `tstride` | 48 |

Capacity is fixed; allocate enough slots for the maximum expected object count.

Pack active records and create the corresponding VAOs/VBOs:

```python
rects, rect_instances = to_gl(rects, rect_instances, "rect")
points, point_instances = to_gl(points, point_instances, "point")
sprites, tex_instances = to_gl(sprites, tex_instances, "tex")

rect_vao, rect_vbo = build_rect_objs(ctx, rect_program, rect_instances)
point_vao, point_vbo = build_point_objs(ctx, point_program, point_instances)
tex_vao, tex_vbo = build_tex_objs(ctx, tex_program, tex_instances)
```

Valid `to_gl()` type strings are `"rect"`, `"point"`, and `"tex"`.

Render only the populated count, not the allocated capacity:

```python
rect_vao.render(moderngl.TRIANGLES, instances=len(rects))
point_vao.render(moderngl.POINTS, vertices=1, instances=len(points))
tex_vao.render(moderngl.TRIANGLES, instances=len(sprites))
```

## Textures and atlases

```python
tex_program = load_program(ctx, "shaders/tex.vert", "shaders/tex.frag")
tex_program["u_viewport_size"] = viewport_size

atlas = load_texture(ctx, "assets/atlas.png")
atlas.use(location=0)

tex_program["u_texture"] = 0
tex_program["u_atlas_grid"] = (4.0, 2.0)
```

`u_atlas_grid` is `(columns, rows)`. Atlas cells must have equal dimensions.
The final two texture-record fields select a zero-based cell. Use
`(1.0, 1.0)` for a texture containing one image.

`load_texture()` loads RGBA data, flips it vertically for OpenGL, and applies
nearest-neighbor filtering. Keep the texture bound to its configured texture
unit while rendering.

## Lines and polygons

Line and polygon points use pygame pixel coordinates:

```python
points = [(x1, y1), (x2, y2), ...]
rgba = (r, g, b, a)
```

Create a shared line/polygon program:

```python
line_program = load_program(ctx, "shaders/line.vert", "shaders/line.frag")
line_program["u_viewport_size"] = viewport_size
```

### Line segments and polylines

```python
segment = [(100, 100), (500, 300)]
segment_vao, segment_vbo = build_line_obj(
    ctx, line_program, segment, (255, 80, 80, 255)
)

segment_vao.render(moderngl.LINES, vertices=len(segment))
```

Connectivity depends on the ModernGL render mode:

| Mode | Behavior |
| --- | --- |
| `moderngl.LINES` | Independent pairs: `0→1`, `2→3`, and so on |
| `moderngl.LINE_STRIP` | Open connected chain: `0→1→2→3` |
| `moderngl.LINE_LOOP` | Closed outline: `0→1→2→3→0` |

Native line widths greater than one pixel are not portable across OpenGL core
drivers. Use rotated rectangles when reliable thickness, joins, or end caps are
required.

### Polygon outlines and fills

```python
polygon = [
    (100, 100),
    (300, 100),
    (350, 250),
    (200, 350),
    (50, 250),
]

polygon_vao, polygon_vbo = build_polygon_obj(
    ctx,
    line_program,
    polygon,
    (255, 200, 80, 180),
)

render_polygon(polygon_vao, polygon, fill=True)
```

`render_polygon()` returns `True` when it filled the polygon and `False` when it
drew an outline.

- `fill=False` always uses `LINE_LOOP`.
- `fill=True` fills simple, non-degenerate convex polygons with
  `TRIANGLE_FAN`.
- Concave, self-intersecting, duplicated, collinear, and two-point inputs fall
  back to an outline.
- Do not repeat the first point when using `render_polygon()`; `LINE_LOOP`
  closes the final edge automatically.

A convex polygon has no inward dents. A concave polygon has at least one
inward-facing corner whose interior angle is greater than 180 degrees. Both may
be outlined, but only convex polygons are filled.

Fill eligibility is cached using point positions relative to the first point.
Translating the whole polygon or changing RGBA reuses the cached result;
changing the polygon's internal shape triggers validation. The cache stores at
most 256 shapes.

### Updating line or polygon geometry

```python
polygon = [(120, 100), (340, 120), (300, 320), (100, 280)]
update_polygon_obj(
    polygon_vbo,
    polygon,
    (255, 120, 40, 180),
)

render_polygon(polygon_vao, polygon, fill=True)
```

`update_line_obj()` has the same behavior for line buffers. Replacement data
may contain the same number or fewer points than the original allocation. If it
contains more, rebuild the VAO and VBO with the larger point list.

## Updating objects

An instance update has three steps:

1. Modify the source record.
2. Pack the record into its NumPy slot with `update_instances()`.
3. Upload that slot with `vbo.write()`.

```python
index = 0

modify_xy(index, sprites, 500, 300)
modify_rgba(index, sprites, 255, 255, 255, 128)
modify_size(index, sprites, 128, 64, "tex")
modify_rot(index, sprites, 45, "tex")
modify_texture(index, sprites, 3, 0, "tex")

tex_instances = update_instances(index, sprites, tex_instances)
tex_vbo.write(
    tex_instances[index].tobytes(),
    offset=index * tstride,
)
```

Mutation helpers change only the source list. `update_instances()` packs the
entire record without changing it. `vbo.write()` makes the change visible on
the GPU.

Available mutation helpers:

| Function | Effect |
| --- | --- |
| `modify_xy(index, data, x, y)` | Set pixel center position |
| `modify_rgba(index, data, r, g, b, a)` | Set 0-255 color and alpha |
| `modify_size(index, data, width, height, type_)` | Set pixel dimensions; points use `width` and ignore `height` |
| `modify_rot(index, data, angle, type_="rect")` | Set rotation in degrees |
| `modify_thickness(index, data, factor, type_="rect")` | Set rectangle border thickness |
| `modify_texture(index, data, tilex, tiley, type_="tex")` | Select an atlas cell |

`modify_scale()` remains as a compatibility alias for `modify_size()`, but its
arguments now represent pixels.

### Adding an object

Append a source record, pack its new slot, and upload it:

```python
points.append([250, 200, 0, 255, 0, 160, 30])
index = len(points) - 1

point_instances = update_instances(index, points, point_instances)
point_vbo.write(point_instances[index].tobytes(), offset=index * pstride)
```

The new length must not exceed the allocated capacity.

### Removing an object

Move the last record into the removed slot, upload that slot, and shorten the
source list:

```python
index = 2
last_index = len(points) - 1

if index != last_index:
    points[index] = points[last_index]
    point_instances[index] = point_instances[last_index]
    point_vbo.write(point_instances[index].tobytes(), offset=index * pstride)

points.pop()
```

Render with `instances=len(points)`. The stale final GPU slot is ignored. This
removal method does not preserve ordering.

## Collision detection

Collision helpers operate directly on pixel-space source records; GPU packing
is not required first.

### Rectangle/texture against rectangles/textures

```python
hits = check_collision(sprites[0], rects, "rect")
```

Use `"rect"` or `"tex"` for rectangle-shaped obstacles. Results contain
`("rt", index)` tuples. Collision accounts for pixel dimensions and rotation.

### Rectangle/texture against points

```python
hits = check_collision(sprites[0], points, "point")
```

Results contain `("p", index)` tuples for points inside the first argument.

### Mouse picking

```python
mouse_x, mouse_y = pygame.mouse.get_pos()

rect_hits = check_mouse_collisions(mouse_x, mouse_y, rects, "rect")
point_hits = check_mouse_collisions(mouse_x, mouse_y, points, "point")
sprite_hits = check_mouse_collisions(mouse_x, mouse_y, sprites, "tex")
```

The result is a list of matching indices in source-list order.

### Convex polygon collision

Vertices must follow the perimeter clockwise or counterclockwise. Concave,
self-intersecting, duplicate, and degenerate polygons raise `ValueError` in the
convex collision helpers.

```python
triangle = [(100, 100), (240, 180), (120, 300)]
hexagon = [
    (500, 180),
    (600, 240),
    (600, 360),
    (500, 420),
    (400, 360),
    (400, 240),
]

polygons_overlap = check_convex_polygon_collision(triangle, hexagon)
polygon_hits_rect = check_convex_polygon_rect_collision(hexagon, rects[0])
```

Touching edges count as a collision.

## Shader interface

Custom shaders must use the attribute names and types expected by the builders.

| Builder | Required vertex attributes |
| --- | --- |
| `build_rect_objs()` | `vec2 quad_position`, `vec2 quad_uv`, `vec2 in_offset`, `vec4 in_color`, `float in_thickness`, `vec2 in_size`, `float in_rotation` |
| `build_point_objs()` | `vec2 in_offset`, `vec4 in_color`, `float in_size` |
| `build_tex_objs()` | Rectangle attributes plus `vec2 in_tile` |
| `build_line_obj()` / `build_polygon_obj()` | `vec2 in_position`, `vec4 in_color` |

Every supplied vertex shader also expects:

```glsl
uniform vec2 u_viewport_size;
```

## API summary

| Function | Purpose |
| --- | --- |
| `set_viewport_size(width, height)` | Update module dimensions and return `(WIDTH, HEIGHT)` |
| `get_new_instances(rn, pn, tn)` | Allocate rectangle, point, and texture instance arrays |
| `load_program(ctx, vert_path, frag_path)` | Compile a vertex/fragment shader pair |
| `load_texture(ctx, path)` | Load a nearest-filtered RGBA texture |
| `to_gl(data, instances, type_)` | Pack all active source records |
| `update_instances(index, data, instances)` | Pack one source record |
| `build_rect_objs(ctx, program, instances)` | Create rectangle VAO and instance VBO |
| `build_point_objs(ctx, program, instances)` | Create point VAO and instance VBO |
| `build_tex_objs(ctx, program, instances)` | Create textured-rectangle VAO and instance VBO |
| `create_line_vertices(points, rgba)` | Pack pixel-space line vertices |
| `build_line_obj(ctx, program, points, rgba)` | Create line VAO and VBO |
| `update_line_obj(vbo, points, rgba)` | Replace line vertices |
| `build_polygon_obj(ctx, program, points, rgba)` | Create polygon VAO and VBO |
| `update_polygon_obj(vbo, points, rgba)` | Replace polygon vertices |
| `render_polygon(vao, points, fill=False)` | Draw an outline or valid convex fill |
| `is_convex_polygon(points)` | Check whether a polygon is fillable |
| `check_collision(player, obstacles, type_)` | Rectangle/texture collision query |
| `check_mouse_collisions(mx, my, data, type_)` | Mouse picking query |
| `check_convex_polygon_collision(poly1, poly2)` | Convex polygon query |
| `check_convex_polygon_rect_collision(polygon, rect)` | Convex polygon/rectangle query |
| `convert_to_clip_space(x, y)` | Optional pixel-to-clip utility; normal APIs do not need it |

## Common problems

- **Nothing is visible:** Set `u_viewport_size`, call `to_gl()` before building
  instance VAOs, and render `len(source_list)` instances.
- **Objects are stretched or misplaced:** Ensure `set_viewport_size()`,
  `ctx.viewport`, and every active program use the actual window size.
- **Points are invisible:** Enable `moderngl.PROGRAM_POINT_SIZE` and render with
  `vertices=1`.
- **Transparency does not work:** Enable `moderngl.BLEND` and configure
  `SRC_ALPHA`, `ONE_MINUS_SRC_ALPHA`.
- **A requested polygon fill becomes an outline:** The input is not a simple,
  non-degenerate convex polygon. The fallback is intentional.
- **A line remains one pixel wide:** The driver does not support wide native
  lines. Use a rotated rectangle for reliable thickness.
- **A new object or line vertex is missing:** The fixed-capacity buffer is too
  small; rebuild it with a larger allocation.
- **An update is not visible:** Pack the record and write its byte range to the
  VBO after changing the source list.
