# `gl_utils` module documentation

`gl_utils.py` provides a small, fixed-layout 2D renderer built on pygame,
ModernGL, and NumPy. It supports instanced rectangles, points, and textured
rectangles; native line segments and polylines; arbitrary polygon outlines;
convex polygon fills; plus picking and collision helpers.

This document describes the module's data contracts, initialization order,
rendering API, update workflow, and collision API.

## Requirements

- Python 3
- OpenGL 3.3 or newer
- `pygame`
- `moderngl`
- `numpy`

Install the dependencies with:

```bash
python -m pip install pygame moderngl numpy
```

The following files must be available relative to the program's working
directory when using the supplied shaders:

```text
gl_utils.py
shaders/
├── point.vert
├── point.frag
├── line.vert
├── line.frag
├── rect.vert
├── rect.frag
├── tex.vert
└── tex.frag
```

## Minimal runnable program

The following program creates a window and draws one rectangle and one point.
It can be used as a starting template.

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


# The OpenGL attributes must be set before creating the window.
pygame.init()
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(
    pygame.GL_CONTEXT_PROFILE_MASK,
    pygame.GL_CONTEXT_PROFILE_CORE,
)
pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

window_width = 800
window_height = 600
screen = pygame.display.set_mode(
    (window_width, window_height),
    pygame.OPENGL | pygame.DOUBLEBUF,
)

# Synchronize gl_utils with the actual drawable window size.
viewport_size = set_viewport_size(*screen.get_size())

ctx = moderngl.create_context()
ctx.viewport = (0, 0, *viewport_size)
ctx.enable(moderngl.PROGRAM_POINT_SIZE)
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

# Compile the supplied shaders.
rect_program = load_program(ctx, "shaders/rect.vert", "shaders/rect.frag")
point_program = load_program(ctx, "shaders/point.vert", "shaders/point.frag")
rect_program["u_viewport_size"] = viewport_size
point_program["u_viewport_size"] = viewport_size

# Define objects in pygame units: pixel positions, 0-255 RGBA, and degrees.
rects = [
    [400, 300, 255, 80, 80, 192, 0.08, 120, 60, 20],
]
points = [
    [400, 300, 255, 255, 255, 255, 20],
]

# Capacities may be larger than the current object counts.
rect_instances, point_instances, unused_tex_instances = get_new_instances(
    100,
    100,
    0,
)

# Pack the active records into the GPU instance arrays.
rects, rect_instances = to_gl(rects, rect_instances, "rect")
points, point_instances = to_gl(points, point_instances, "point")

# Create the VAOs and GPU instance buffers.
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

## Required lifecycle

Use the module in this order:

1. Configure pygame for an OpenGL 3.3 core context.
2. Create the pygame/OpenGL window at the desired size.
3. Call `set_viewport_size(*screen.get_size())`.
4. Create the ModernGL context and set `ctx.viewport` from the viewport size.
5. Load the required shader programs with `load_program()`.
6. Enable blending and configure the blend function if alpha should produce
   translucency.
7. Set the returned size as `u_viewport_size` on every program being used.
8. Create Python object lists in pygame units.
9. Allocate fixed-capacity arrays with `get_new_instances()`.
10. Call `to_gl()` once for each object list.
11. Create VAOs and VBOs with the matching `build_*_objs()` function.
12. Render only `len(object_list)` instances.
13. For later changes, update the Python record, its NumPy slot, and its GPU
    buffer slot in that order.

## Coordinate and value conventions

Object records always use these public-facing units:

| Value | Input convention |
| --- | --- |
| Position | pygame pixels; origin at the top left; positive Y points down |
| RGBA color | integers or floats in the range 0-255 |
| Rotation | degrees |
| Width, height, point size | pixels |
| Thickness | normalized quad UV value; no conversion is performed |
| Atlas tile | zero-based column and row; no conversion is performed |

`to_gl()` does not mutate these records. It copies them into a separate NumPy
instance array, normalizing RGBA and converting rotation to radians only in the
GPU copy. Positions and dimensions remain pixels in both copies.

### Window size

The module defaults to:

```python
WIDTH, HEIGHT = 800, 600
aspect = WIDTH / HEIGHT
```

Configure another size without editing `gl_utils.py`:

```python
screen = pygame.display.set_mode(
    (1280, 720),
    pygame.OPENGL | pygame.DOUBLEBUF,
)
viewport_size = set_viewport_size(*screen.get_size())
```

`set_viewport_size()` updates the module's internal `WIDTH`, `HEIGHT`, and
`aspect`, then returns `(WIDTH, HEIGHT)`. Use that tuple for every shader:

Use the returned value for the rectangle and texture shader uniforms:

```python
rect_program["u_viewport_size"] = viewport_size
point_program["u_viewport_size"] = viewport_size
tex_program["u_viewport_size"] = viewport_size
line_program["u_viewport_size"] = viewport_size
```

Because GPU positions and sizes remain in pixels, a runtime resize only requires
calling `set_viewport_size()`, updating `ctx.viewport`, and assigning the new
tuple to each program's `u_viewport_size`. Existing object and line buffers do
not need to be rebuilt.

## Object record schemas

Each object is represented by a mutable Python list. Field order is part of the
module API.

### Rectangle

```text
[x, y, r, g, b, a, thickness, width, height, rotation]
```

Example:

```python
rect = [200, 150, 255, 0, 0, 128, 0.08, 100, 50, 45]
```

| Index | Field | Meaning |
| ---: | --- | --- |
| 0-1 | `x`, `y` | Center position |
| 2-5 | `r`, `g`, `b`, `a` | Color and alpha |
| 6 | `thickness` | Border thickness |
| 7-8 | `width`, `height` | Pixel dimensions |
| 9 | `rotation` | Rotation about the center |

`thickness=0` draws a filled rectangle. Values between `0` and `0.5` draw a
border, with larger values producing a thicker border. Values around `0.5` or
higher cover essentially the entire rectangle.

Rectangle dimensions remain the same number of pixels at every window size.

### Point

```text
[x, y, r, g, b, a, size]
```

Example:

```python
point = [100, 100, 255, 255, 255, 255, 20]
```

Point `size` is its width and height in pixels. Call
`ctx.enable(moderngl.PROGRAM_POINT_SIZE)` before rendering points.

### Textured rectangle

```text
[x, y, r, g, b, a, unused, width, height, rotation, tile_x, tile_y]
```

Example:

```python
sprite = [320, 240, 255, 255, 255, 200, 0, 64, 64, 0, 2, 1]
```

The seventh field exists to keep the textured layout compatible with the quad
layout but is not used by the supplied texture fragment shader. RGB values tint
the sampled texture, and the instance alpha multiplies the texture alpha. Use
white `(255, 255, 255)` to preserve the texture's original RGB color.

`tile_x` and `tile_y` select a cell from a uniform texture atlas.

### Lines, polylines, and polygons

Lines use a list of pygame pixel-coordinate pairs rather than a fixed object
record:

```python
points = [(x1, y1), (x2, y2), ...]
rgba = (r, g, b, a)
```

The same point list can be rendered in three ways:

| Render mode | Interpretation |
| --- | --- |
| `moderngl.LINES` | Each pair of points is an independent segment: `0→1`, `2→3`, and so on. |
| `moderngl.LINE_STRIP` | An open chain: `0→1→2→3`. |
| `moderngl.LINE_LOOP` | A closed polygon outline: `0→1→2→3→0`. |
| `moderngl.TRIANGLE_FAN` | A filled convex polygon using the same perimeter points. |

A single line segment contains two coordinate pairs:

```python
segment = [(100, 100), (500, 300)]
```

A hexagon contains six coordinate pairs when rendered with `LINE_LOOP`. Do not
repeat the first point because `LINE_LOOP` closes the last edge automatically.
If the same shape is rendered with `LINE_STRIP`, repeat the first point as a
seventh entry to close it.

### Convex and concave polygons

Only **convex** polygons can be filled by `gl_utils`. A convex polygon has no
inward dents: every interior angle is at most 180 degrees, and a line drawn
between any two points inside the polygon remains inside it.

```python
convex = [
    (100, 100),
    (220, 80),
    (280, 180),
    (200, 260),
    (80, 220),
]
```

A **concave** polygon has at least one inward-facing corner, or dent. At that
corner the interior angle is greater than 180 degrees.

```python
concave = [
    (100, 100),
    (280, 100),
    (190, 180),  # Inward-facing corner
    (280, 260),
    (100, 260),
]
```

Both shapes can be drawn as outlines. If `fill=True` is requested for the
concave example, `render_polygon()` detects that it is not convex and silently
draws its outline instead.

Lines and polygons do not use the instanced object arrays. Convex polygon
collision can use the same point list, but collision is independent of the
rendered line width.

## Creating instance storage

```python
rect_instances, point_instances, tex_instances = get_new_instances(
    rect_capacity,
    point_capacity,
    texture_capacity,
)
```

The returned arrays use `numpy.float32` and have these shapes:

| Type | Shape | Stride constant | Bytes per record |
| --- | --- | --- | ---: |
| Rectangle | `(rect_capacity, 10)` | `rstride` | 40 |
| Point | `(point_capacity, 7)` | `pstride` | 28 |
| Texture | `(texture_capacity, 12)` | `tstride` | 48 |

Capacity is fixed. `gl_utils` does not grow these arrays automatically. Choose
a capacity greater than or equal to the maximum expected object count.

## Packing initial data

Use `to_gl(data, instances, type_)` to pack records before building GPU objects:

```python
rects, rect_instances = to_gl(rects, rect_instances, "rect")
points, point_instances = to_gl(points, point_instances, "point")
sprites, tex_instances = to_gl(sprites, tex_instances, "tex")
```

Valid type strings are:

- `"rect"` for rectangle records
- `"point"` for point records
- `"tex"` for textured rectangle records

The function leaves `data` in pixel/RGBA/degree units, fills the corresponding
beginning of `instances`, and returns both objects.

## Creating GPU objects

Each builder returns a ModernGL vertex array object and the instance VBO:

```python
rect_vao, rect_vbo = build_rect_objs(ctx, rect_program, rect_instances)
point_vao, point_vbo = build_point_objs(ctx, point_program, point_instances)
tex_vao, tex_vbo = build_tex_objs(ctx, tex_program, tex_instances)
```

Keep both returned objects. Use the VAO for rendering and the VBO for partial
updates.

Lines use `build_line_obj()` instead of an instance array:

```python
line_program = load_program(ctx, "shaders/line.vert", "shaders/line.frag")

polygon = [(100, 100), (300, 100), (350, 250), (200, 350), (50, 250)]
polygon_vao, polygon_vbo = build_line_obj(
    ctx,
    line_program,
    polygon,
    (255, 200, 80, 255),
)
```

`build_line_obj()` stores pygame pixel coordinates and normalizes the 0-255 RGBA
color. Do not call `to_gl()` on line points. Coordinates stay in pixels in the
line VBO.

For a polygon, use `build_polygon_obj()`. It has the same return values and data
format. At least two points are required for an outline:

```python
polygon_vao, polygon_vbo = build_polygon_obj(
    ctx,
    line_program,
    polygon,
    (255, 200, 80, 160),
)
```

### Required shader interfaces

Custom shaders may be used, but their attribute names and layouts must match
the builders.

Rectangle vertex shader inputs:

```glsl
in vec2 quad_position;
in vec2 quad_uv;
in vec2 in_offset;
in vec4 in_color;
in float in_thickness;
in vec2 in_size;
in float in_rotation;
```

Point vertex shader inputs:

```glsl
in vec2 in_offset;
in vec4 in_color;
in float in_size;
```

Line vertex shader inputs:

```glsl
in vec2 in_position;
in vec4 in_color;
```

Texture vertex shader inputs:

```glsl
in vec2 quad_position;
in vec2 quad_uv;
in vec2 in_offset;
in vec4 in_color;
in float in_thickness;
in vec2 in_size;
in float in_rotation;
in vec2 in_tile;
```

Every supplied vertex shader requires:

```glsl
uniform vec2 u_viewport_size;
```

Set it before rendering:

```python
rect_program["u_viewport_size"] = viewport_size
point_program["u_viewport_size"] = viewport_size
tex_program["u_viewport_size"] = viewport_size
line_program["u_viewport_size"] = viewport_size
```

## Rendering

Render the number of populated records, not the allocated capacity:

```python
rect_vao.render(moderngl.TRIANGLES, instances=len(rects))
point_vao.render(moderngl.POINTS, vertices=1, instances=len(points))
tex_vao.render(moderngl.TRIANGLES, instances=len(sprites))
```

Rendering the capacity would also draw the unused zero-filled records.

Render line data with a mode matching the intended connectivity:

```python
# Exactly one segment when segment contains two points.
segment_vao.render(moderngl.LINES, vertices=len(segment))

# Every adjacent point is connected; the ends remain open.
polyline_vao.render(moderngl.LINE_STRIP, vertices=len(polyline))

# Every adjacent point is connected and the last connects to the first.
render_polygon(polygon_vao, polygon, fill=False)

# Fill the same convex polygon using its RGBA color.
render_polygon(polygon_vao, polygon, fill=True)
```

`render_polygon()` uses `LINE_LOOP` for an outline. When `fill=True`, it first
checks whether the points describe a simple, non-degenerate convex polygon. A
valid polygon uses `TRIANGLE_FAN`; otherwise the function automatically falls
back to `LINE_LOOP`. Its Boolean return value indicates whether filling occurred.
The fill result is cached using every point relative to the first point. Moving
the whole polygon or changing RGBA reuses the cached result; changing its
internal shape triggers validation. The cache retains at most 256 shapes.
Polygon rendering always closes the last point back to the first; an open
polyline has no interior and cannot be filled. Use `LINE_STRIP` for open data.

Native line width is context-wide:

```python
ctx.line_width = 1.0
```

Many OpenGL core-profile drivers support only a width of `1.0`, even when a
larger value is requested. Use rotated rectangles when consistent thick lines,
custom joins, or custom end caps are required.

### Alpha blending

Every object record contains alpha in the 0-255 range. Enable
standard source-over blending once after creating the context:

```python
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
```

An alpha of `255` is fully opaque, `0` is fully transparent, and values between
them are translucent. Objects are blended in draw order, so draw background
objects before foreground objects. The module does not sort transparent objects.

## Loading textures and atlases

`load_texture(ctx, path)` loads an image as RGBA, flips it vertically for
OpenGL, and applies nearest-neighbor filtering.

```python
atlas = load_texture(ctx, "assets/atlas.png")
atlas.use(location=0)

tex_program["u_texture"] = 0
tex_program["u_atlas_grid"] = (4.0, 2.0)
```

`u_atlas_grid` is `(columns, rows)`. All atlas cells must have the same size.
The texture record's `tile_x` and `tile_y` fields are zero-based cell
coordinates. Use `(1.0, 1.0)` for a texture containing a single image.

Complete texture setup:

```python
tex_program = load_program(ctx, "shaders/tex.vert", "shaders/tex.frag")
tex_program["u_viewport_size"] = viewport_size

atlas = load_texture(ctx, "assets/atlas.png")
atlas.use(location=0)
tex_program["u_texture"] = 0
tex_program["u_atlas_grid"] = (4.0, 2.0)

sprites = [
    [320, 240, 255, 255, 255, 255, 0, 64, 64, 0, 2, 1],
]

rect_instances, point_instances, tex_instances = get_new_instances(0, 0, 100)
sprites, tex_instances = to_gl(sprites, tex_instances, "tex")
tex_vao, tex_vbo = build_tex_objs(ctx, tex_program, tex_instances)
```

The texture must remain bound to the configured texture unit while rendering.

## Updating a line or polygon

`update_line_obj(vbo, points, rgba)` replaces line vertex data and returns the
new vertex count. Use `update_polygon_obj()` for a polygon; it applies the same
update and permits any outline containing at least two points:

```python
from gl_utils import render_polygon, update_polygon_obj

polygon = [(120, 100), (340, 120), (300, 320), (100, 280)]
update_polygon_obj(
    polygon_vbo,
    polygon,
    (255, 120, 40, 180),
)

render_polygon(polygon_vao, polygon, fill=True)
```

The updated data may contain the same number or fewer points than the data used
to create the buffer. If it contains more points, rebuild the VAO and VBO with
`build_polygon_obj()` so the GPU buffer is large enough. Always render the
updated point list so `render_polygon()` uses the new vertex count.

## Updating an existing object

An update has three required steps:

1. Change the Python record.
2. Copy the changed record into its NumPy instance slot with
   `update_instances()`.
3. Upload that slot to the instance VBO with `vbo.write()`.

### Change a position

`modify_xy()` accepts a new pixel position:

```python
from gl_utils import modify_xy, tstride, update_instances

index = 0
sprites = modify_xy(index, sprites, 500, 300)
tex_instances = update_instances(index, sprites, tex_instances)
tex_vbo.write(tex_instances[index].tobytes(), offset=index * tstride)
```

### Change a color or alpha

`modify_rgba()` accepts RGBA values in the 0-255 range:

```python
from gl_utils import modify_rgba, rstride, update_instances

index = 0
rects = modify_rgba(index, rects, 255, 0, 255, 128)
rect_instances = update_instances(index, rects, rect_instances)
rect_vbo.write(rect_instances[index].tobytes(), offset=index * rstride)
```

### Change a rotation

`modify_rot()` accepts degrees:

```python
rects = modify_rot(index, rects, 45, "rect")
rect_instances = update_instances(index, rects, rect_instances)
rect_vbo.write(rect_instances[index].tobytes(), offset=index * rstride)
```

### Change size, thickness, or atlas tile

Sizes are specified directly in pixels:

```python
sprites = modify_size(index, sprites, 128, 64, "tex")
sprites = modify_texture(index, sprites, 3, 0, "tex")
tex_instances = update_instances(index, sprites, tex_instances)
tex_vbo.write(tex_instances[index].tobytes(), offset=index * tstride)
```

Every update repacks the complete record into GPU form without changing the
source list. No field-specific conversion flags are needed.

## Adding an object after initialization

Append a record in public-facing units, pack its new slot, and upload that slot:

```python
from gl_utils import pstride, update_instances

points.append([250, 200, 0, 255, 0, 160, 30])
index = len(points) - 1

point_instances = update_instances(index, points, point_instances)
point_vbo.write(point_instances[index].tobytes(), offset=index * pstride)
```

The new length must not exceed the allocated capacity.

## Removing an object

The renderer draws the first `len(data)` instance slots. To remove an object
without shifting every later GPU record, move the last record into the removed
slot and then shorten the list:

```python
index = 2
last_index = len(points) - 1

if index != last_index:
    points[index] = points[last_index]
    point_instances[index] = point_instances[last_index]
    point_vbo.write(point_instances[index].tobytes(), offset=index * pstride)

points.pop()
```

No GPU clearing is needed because rendering now uses the shorter list length.
This removal method does not preserve object order.

## Mutation helper reference

All mutation helpers modify `data` in place and also return it. They do not
update the NumPy array or GPU buffer.

### `modify_xy(index, data, x, y)`

Replaces fields 0 and 1 with pixel coordinates.

### `modify_rgba(index, data, r, g, b, a)`

Replaces fields 2 through 5 with 0-255 color and alpha values.

### `modify_size(index, data, width, height, type_)`

For `"rect"` and `"tex"`, replaces fields 7 and 8 with pixel dimensions. For
`"point"`, replaces field 6 with `width`; `height` is ignored.

`modify_scale()` remains as a compatibility alias but now has the same
pixel-size behavior.

### `modify_rot(index, data, angle, type_="rect")`

For `"rect"` and `"tex"`, replaces field 9 with an angle in degrees.

### `modify_thickness(index, data, factor, type_="rect")`

For `"rect"`, replaces field 6. Other types are unchanged.

### `modify_texture(index, data, tilex, tiley, type_="tex")`

For `"tex"`, replaces fields 10 and 11. Other types are unchanged.

## Collision detection

Collision functions operate directly on the public pixel-space records. They do
not require `to_gl()` or `update_instances()` first.

### Rectangle or texture against rectangles/textures

```python
from gl_utils import check_collision

hits = check_collision(sprites[0], rects, "rect")
```

The first argument is the rectangle-shaped object being checked. The second is
the obstacle list. Use either `"rect"` or `"tex"` for rectangle-shaped
obstacles. Rotated rectangle collision uses the separating axis theorem and
accounts for pixel dimensions and rotation.

The return value contains `("rt", index)` tuples:

```python
[("rt", 0), ("rt", 2)]
```

### Rectangle or texture against points

```python
hits = check_collision(sprites[0], points, "point")
```

The return value contains `("p", index)` tuples for points inside the first
argument:

```python
[("p", 1)]
```

### Convex polygon collision

Polygon collision is intentionally limited to convex polygons. List vertices in
clockwise or counterclockwise perimeter order and do not include interior
points. The same pygame-coordinate point lists used by `build_line_obj()` may be
passed directly to the collision helpers.

Check two convex polygons:

```python
from gl_utils import check_convex_polygon_collision

triangle = [(100, 100), (240, 180), (120, 300)]
hexagon = [(500, 180), (600, 240), (600, 360),
           (500, 420), (400, 360), (400, 240)]

if check_convex_polygon_collision(triangle, hexagon):
    print("The polygons overlap")
```

Check a convex polygon against a pixel-space rectangle or textured-rectangle
record:

```python
from gl_utils import check_convex_polygon_rect_collision

if check_convex_polygon_rect_collision(hexagon, rects[0]):
    print("The hexagon overlaps the rectangle")
```

Both functions return a Boolean and count touching edges as a collision. They
operate directly in pygame pixels. Concave and self-intersecting polygons are
unsupported and raise `ValueError`.

### Mouse picking

`check_mouse_collisions()` accepts the mouse position and object records in
pygame pixels:

```python
from gl_utils import check_mouse_collisions

mouse_x, mouse_y = pygame.mouse.get_pos()
rect_hits = check_mouse_collisions(mouse_x, mouse_y, rects, "rect")
point_hits = check_mouse_collisions(mouse_x, mouse_y, points, "point")
sprite_hits = check_mouse_collisions(mouse_x, mouse_y, sprites, "tex")
```

It returns matching indices in object-list order. More than one object may be
returned when objects overlap.

### Low-level geometry functions

The following functions are exposed but are normally used internally:

- `point_in_rotated_rect(px, py, cx, cy, width, height, rotation)` returns a
  Boolean. Coordinates and dimensions are pixels; rotation is degrees.
- `get_rect_corners(cx, cy, width, height, rotation)` returns four pixel-space
  corner tuples.
- `sat_collision(poly1, poly2)` returns whether two convex polygons overlap.
- `_project()` and `_overlap_on_axis()` are internal SAT helpers.

## API reference

### `get_new_instances(rn, pn, tn)`

Allocates and returns the rectangle, point, and texture NumPy instance arrays.
The arguments specify capacities.

### `load_program(ctx, vert_path, frag_path)`

Reads the two shader files and returns `ctx.program(...)`. File, shader
compilation, and program linking errors propagate to the caller.

### `build_rect_objs(ctx, program, instances)`

Builds rectangle quad geometry and returns `(vao, instance_vbo)`.

### `build_point_objs(ctx, program, instances)`

Builds a point VAO and returns `(vao, instance_vbo)`.

### `create_line_vertices(points, rgba)`

Packs a sequence of pygame `(x, y)` pairs and one 0-255 RGBA color into an
interleaved `float32` array with the layout `[x_px, y_px, r, g, b, a]`.
At least two points and exactly four color components are required.

### `build_line_obj(ctx, program, points, rgba)`

Creates a dynamic, non-instanced line VBO and its VAO. Returns `(vao, vbo)`.
The shader must expose `in_position` as `vec2` and `in_color` as `vec4`.

### `update_line_obj(vbo, points, rgba)`

Packs and uploads replacement line vertices, then returns the vertex count.
The replacement data cannot be larger than the VBO created by
`build_line_obj()`.

### `build_polygon_obj(ctx, program, points, rgba)`

Creates a polygon VAO and dynamic VBO from at least two pygame-coordinate points
and a 0-255 RGBA color. Concave, self-intersecting, duplicate, and collinear
points are allowed for outline rendering. Returns `(vao, vbo)`.

### `update_polygon_obj(vbo, points, rgba)`

Replaces polygon vertices and returns the new vertex count. Arbitrary outline
geometry is allowed, but the replacement cannot exceed the VBO's original
capacity.

### `is_convex_polygon(points)`

Returns whether the points form a simple, non-degenerate convex polygon. It
returns `False` for fewer than three points, duplicate points,
self-intersections, collinear polygons, and inconsistent turn directions.

### `render_polygon(vao, points, fill=False)`

Draws a closed `LINE_LOOP` outline when `fill=False`. With `fill=True`, it draws
a `TRIANGLE_FAN` only when `is_convex_polygon(points)` is true; otherwise it
falls back to an outline. Returns `True` when filled and `False` when outlined.
At least two points are required. Fill validation is cached by relative point
positions, so uniform translation and RGBA changes do not repeat validation.

### `build_tex_objs(ctx, program, instances)`

Builds textured-quad geometry and returns `(vao, instance_vbo)`.

### `set_viewport_size(width, height)`

Updates the module-level `WIDTH`, `HEIGHT`, and `aspect` values and returns the
integer `(WIDTH, HEIGHT)` tuple for shader uniforms. Width and height must be
positive:

```python
viewport_size = set_viewport_size(*screen.get_size())
```

### `convert_to_clip_space(x, y)`

Converts pygame pixels to clip space using `WIDTH` and `HEIGHT`. Returns
`(clip_x, clip_y)`. The standard object, line, polygon, and collision APIs are
pixel-native and do not require this helper.

### `to_gl(data, instances, type_)`

Packs every populated record into `instances` and returns `(data, instances)`.
The source records remain in pixel, 0-255 RGBA, and degree units.

### `update_instances(idx, data, instances)`

Packs one complete record into `instances[idx]` and returns `instances`. It
normalizes RGBA and converts rectangle/texture rotation to radians in the GPU
copy. It does not mutate the source record or write to the GPU.

### `load_texture(ctx, path)`

Loads an RGBA image and returns a nearest-filtered ModernGL texture.

### `check_collision(player, obstacles, type_)`

Returns typed obstacle-index tuples for all collisions with `player`.

### `check_mouse_collisions(mx, my, data, type_)`

Returns the indices of all objects containing the supplied mouse position.

### `check_convex_polygon_collision(poly1, poly2)`

Returns whether two convex pygame-coordinate polygons overlap. Each polygon
requires at least three perimeter-ordered points.

### `check_convex_polygon_rect_collision(polygon, rect)`

Returns whether a convex pygame-coordinate polygon overlaps a pixel-space
rectangle or texture record.

## Common failure cases

- **Nothing is visible:** Confirm that the correct VAO is rendered with
  `instances=len(data)`, the object list is not empty, and `to_gl()` ran before
  the VAO was built.
- **Objects are stretched or misplaced:** Call
  `viewport_size = set_viewport_size(*screen.get_size())` and assign that tuple
  to every active program's `u_viewport_size` uniform.
- **Points are the wrong size or invisible:** Enable
  `moderngl.PROGRAM_POINT_SIZE` and render with `vertices=1`.
- **A polygon is missing its closing edge:** Render it with `LINE_LOOP`, or
  repeat the first point at the end when using `LINE_STRIP`.
- **A polygon requested with `fill=True` appears only as an outline:** Its points
  are concave, degenerate, self-intersecting, duplicated, or otherwise invalid
  for convex triangle-fan filling. This fallback is intentional.
- **Convex polygon collision raises `ValueError`:** Collision remains
  convex-only. Ensure the polygon is simple, non-degenerate, and follows its
  perimeter in clockwise or counterclockwise order.
- **Requested thick lines remain one pixel wide:** The OpenGL driver does not
  support wide native lines. Use rotated filled rectangles for reliable width.
- **Updating a line raises a buffer-size error:** Rebuild it with
  `build_line_obj()` using the larger point list.
- **An updated object has the wrong size:** Rectangle and texture dimensions,
  and point size, are pixels rather than scale factors.
- **An update does not appear:** Writing to the Python list or NumPy array alone
  is insufficient. Upload the record with `vbo.write()`.
- **A buffer write fails or a new object is missing:** The object count may have
  exceeded the capacity passed to `get_new_instances()`.
- **A texture is black, white, or missing:** Bind it to the same unit assigned to
  `u_texture`, set `u_atlas_grid`, and verify the atlas tile coordinates.
- **Shader creation fails:** Custom shader attributes must exactly match the
  names and types required by the corresponding builder.
