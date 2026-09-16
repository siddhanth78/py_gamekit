# `gl_utils` module documentation

`gl_utils.py` provides a small, fixed-layout 2D renderer built on pygame,
ModernGL, and NumPy. It supports instanced rectangles, points, and textured
rectangles, plus picking and collision helpers.

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
    HEIGHT,
    WIDTH,
    aspect,
    build_point_objs,
    build_rect_objs,
    get_new_instances,
    load_program,
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

screen = pygame.display.set_mode(
    (WIDTH, HEIGHT),
    pygame.OPENGL | pygame.DOUBLEBUF,
)

ctx = moderngl.create_context()
ctx.enable(moderngl.PROGRAM_POINT_SIZE)

# Compile the supplied shaders.
rect_program = load_program(ctx, "shaders/rect.vert", "shaders/rect.frag")
point_program = load_program(ctx, "shaders/point.vert", "shaders/point.frag")
rect_program["u_aspect"] = aspect

# Define objects in pygame units: pixel positions, 0-255 RGB, and degrees.
rects = [
    [400, 300, 255, 80, 80, 0.08, 2.0, 1.0, 20],
]
points = [
    [400, 300, 255, 255, 255, 1.0],
]

# Capacities may be larger than the current object counts.
rect_instances, point_instances, unused_tex_instances = get_new_instances(
    100,
    100,
    0,
)

# Convert the active records and copy them into the instance arrays.
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
2. Create a window whose size matches `WIDTH` and `HEIGHT`.
3. Create the ModernGL context.
4. Load the required shader programs with `load_program()`.
5. Set the `u_aspect` uniform on rectangle and texture programs.
6. Create Python object lists in pygame units.
7. Allocate fixed-capacity arrays with `get_new_instances()`.
8. Call `to_gl()` once for each object list.
9. Create VAOs and VBOs with the matching `build_*_objs()` function.
10. Render only `len(object_list)` instances.
11. For later changes, update the Python record, its NumPy slot, and its GPU
    buffer slot in that order.

## Coordinate and value conventions

Before `to_gl()` is called, records use these public-facing units:

| Value | Input convention |
| --- | --- |
| Position | pygame pixels; origin at the top left; positive Y points down |
| RGB color | integers or floats in the range 0-255 |
| Rotation | degrees |
| Scale | multiplier; no conversion is performed |
| Thickness | normalized quad UV value; no conversion is performed |
| Atlas tile | zero-based column and row; no conversion is performed |

`to_gl()` mutates the records in place. After conversion:

| Value | Stored convention |
| --- | --- |
| Position | OpenGL clip space |
| RGB color | normalized floats in the range 0-1 |
| Rotation | radians |
| Scale, thickness, tile | unchanged |

Do not call `to_gl()` twice on the same records. Doing so converts values that
are already converted.

### Window size

The module defines:

```python
WIDTH, HEIGHT = 800, 600
aspect = WIDTH / HEIGHT
```

`convert_to_clip_space()` and all collision calculations use these values. The
pygame window must use the same dimensions. To use another resolution, change
`WIDTH` and `HEIGHT` in `gl_utils.py` before creating data and ensure that shader
uniforms receive the updated `aspect`.

## Object record schemas

Each object is represented by a mutable Python list. Field order is part of the
module API.

### Rectangle

```text
[x, y, r, g, b, thickness, scale_x, scale_y, rotation]
```

Example before conversion:

```python
rect = [200, 150, 255, 0, 0, 0.08, 1.0, 0.5, 45]
```

| Index | Field | Meaning |
| ---: | --- | --- |
| 0-1 | `x`, `y` | Center position |
| 2-4 | `r`, `g`, `b` | Color |
| 5 | `thickness` | Border thickness |
| 6-7 | `scale_x`, `scale_y` | Quad scale |
| 8 | `rotation` | Rotation about the center |

`thickness=0` draws a filled rectangle. Values between `0` and `0.5` draw a
border, with larger values producing a thicker border. Values around `0.5` or
higher cover essentially the entire rectangle.

At scale `(1, 1)`, the rectangle is a square whose width and height are 10% of
the configured window height. Scale is applied independently to each axis.

### Point

```text
[x, y, r, g, b, scale]
```

Example before conversion:

```python
point = [100, 100, 255, 255, 255, 1.0]
```

Point size is `scale * 20` pixels. Call
`ctx.enable(moderngl.PROGRAM_POINT_SIZE)` before rendering points.

### Textured rectangle

```text
[x, y, r, g, b, unused, scale_x, scale_y, rotation, tile_x, tile_y]
```

Example before conversion:

```python
sprite = [320, 240, 255, 255, 255, 0, 1.0, 1.0, 0, 2, 1]
```

The sixth field exists to keep the textured layout compatible with the quad
layout but is not used by the supplied texture fragment shader. RGB values tint
the sampled texture. Use white `(255, 255, 255)` to preserve its original color.

`tile_x` and `tile_y` select a cell from a uniform texture atlas.

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
| Rectangle | `(rect_capacity, 9)` | `rstride` | 36 |
| Point | `(point_capacity, 6)` | `pstride` | 24 |
| Texture | `(texture_capacity, 11)` | `tstride` | 44 |

Capacity is fixed. `gl_utils` does not grow these arrays automatically. Choose
a capacity greater than or equal to the maximum expected object count.

## Initial data conversion

Use `to_gl(data, instances, type_)` before building GPU objects:

```python
rects, rect_instances = to_gl(rects, rect_instances, "rect")
points, point_instances = to_gl(points, point_instances, "point")
sprites, tex_instances = to_gl(sprites, tex_instances, "tex")
```

Valid type strings are:

- `"rect"` for rectangle records
- `"point"` for point records
- `"tex"` for textured rectangle records

The function mutates `data`, fills the corresponding beginning of `instances`,
and returns both objects.

## Creating GPU objects

Each builder returns a ModernGL vertex array object and the instance VBO:

```python
rect_vao, rect_vbo = build_rect_objs(ctx, rect_program, rect_instances)
point_vao, point_vbo = build_point_objs(ctx, point_program, point_instances)
tex_vao, tex_vbo = build_tex_objs(ctx, tex_program, tex_instances)
```

Keep both returned objects. Use the VAO for rendering and the VBO for partial
updates.

### Required shader interfaces

Custom shaders may be used, but their attribute names and layouts must match
the builders.

Rectangle vertex shader inputs:

```glsl
in vec2 quad_position;
in vec2 quad_uv;
in vec2 in_offset;
in vec3 in_color;
in float in_thickness;
in vec2 in_scale;
in float in_rotation;
```

Point vertex shader inputs:

```glsl
in vec2 in_offset;
in vec3 in_color;
in float in_scale;
```

Texture vertex shader inputs:

```glsl
in vec2 quad_position;
in vec2 quad_uv;
in vec2 in_offset;
in vec3 in_color;
in float in_thickness;
in vec2 in_scale;
in float in_rotation;
in vec2 in_tile;
```

The supplied rectangle and texture vertex shaders also require:

```glsl
uniform float u_aspect;
```

Set it before rendering:

```python
rect_program["u_aspect"] = aspect
tex_program["u_aspect"] = aspect
```

## Rendering

Render the number of populated records, not the allocated capacity:

```python
rect_vao.render(moderngl.TRIANGLES, instances=len(rects))
point_vao.render(moderngl.POINTS, vertices=1, instances=len(points))
tex_vao.render(moderngl.TRIANGLES, instances=len(sprites))
```

Rendering the capacity would also draw the unused zero-filled records.

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
tex_program["u_aspect"] = aspect

atlas = load_texture(ctx, "assets/atlas.png")
atlas.use(location=0)
tex_program["u_texture"] = 0
tex_program["u_atlas_grid"] = (4.0, 2.0)

sprites = [
    [320, 240, 255, 255, 255, 0, 1.0, 1.0, 0, 2, 1],
]

rect_instances, point_instances, tex_instances = get_new_instances(0, 0, 100)
sprites, tex_instances = to_gl(sprites, tex_instances, "tex")
tex_vao, tex_vbo = build_tex_objs(ctx, tex_program, tex_instances)
```

The texture must remain bound to the configured texture unit while rendering.

## Updating an existing object

An update has three required steps:

1. Change the Python record.
2. Copy the changed record into its NumPy instance slot with
   `update_instances()`.
3. Upload that slot to the instance VBO with `vbo.write()`.

### Change a position

`modify_xy()` accepts a new pixel position. Convert only the changed position:

```python
from gl_utils import modify_xy, tstride, update_instances

index = 0
sprites = modify_xy(index, sprites, 500, 300)
tex_instances = update_instances(
    index,
    sprites,
    tex_instances,
    convert_xy=True,
    convert_rgb=False,
    convert_rot=False,
)
tex_vbo.write(tex_instances[index].tobytes(), offset=index * tstride)
```

### Change a color

`modify_rgb()` accepts RGB values in the 0-255 range. Convert only the changed
color:

```python
from gl_utils import modify_rgb, rstride, update_instances

index = 0
rects = modify_rgb(index, rects, 255, 0, 255)
rect_instances = update_instances(
    index,
    rects,
    rect_instances,
    convert_xy=False,
    convert_rgb=True,
    convert_rot=False,
)
rect_vbo.write(rect_instances[index].tobytes(), offset=index * rstride)
```

### Change a rotation

`modify_rot()` accepts degrees. Convert only the changed rotation:

```python
rects = modify_rot(index, rects, 45, "rect")
rect_instances = update_instances(
    index,
    rects,
    rect_instances,
    convert_xy=False,
    convert_rgb=False,
    convert_rot=True,
)
rect_vbo.write(rect_instances[index].tobytes(), offset=index * rstride)
```

### Change scale, thickness, or atlas tile

These values require no conversion. Disable all conversions:

```python
sprites = modify_scale(index, sprites, 2.0, 1.0, "tex")
sprites = modify_texture(index, sprites, 3, 0, "tex")
tex_instances = update_instances(
    index,
    sprites,
    tex_instances,
    convert_xy=False,
    convert_rgb=False,
    convert_rot=False,
)
tex_vbo.write(tex_instances[index].tobytes(), offset=index * tstride)
```

The conversion flags are important because the Python list remains in converted
form after `to_gl()`. Re-converting an unchanged position, color, or rotation
will corrupt that value.

## Adding an object after initialization

Append a record in public-facing units, update its new slot with all applicable
conversions enabled, and upload that slot:

```python
from gl_utils import pstride, update_instances

points.append([250, 200, 0, 255, 0, 1.5])
index = len(points) - 1

point_instances = update_instances(
    index,
    points,
    point_instances,
    convert_xy=True,
    convert_rgb=True,
    convert_rot=False,  # Point records have no rotation field.
)
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

Replaces fields 0 and 1. Supply pixel coordinates and enable `convert_xy` in the
following `update_instances()` call.

### `modify_rgb(index, data, r, g, b)`

Replaces fields 2 through 4. Supply 0-255 color values and enable `convert_rgb`
in the following update.

### `modify_scale(index, data, sx, sy, type_)`

For `"rect"` and `"tex"`, replaces fields 6 and 7. For `"point"`, replaces
field 5 with `sx`; `sy` is ignored.

### `modify_rot(index, data, angle, type_="rect")`

For `"rect"` and `"tex"`, replaces field 8. Supply degrees and enable
`convert_rot` in the following update.

### `modify_thickness(index, data, factor, type_="rect")`

For `"rect"`, replaces field 5. Other types are unchanged.

### `modify_texture(index, data, tilex, tiley, type_="tex")`

For `"tex"`, replaces fields 9 and 10. Other types are unchanged.

## Collision detection

Collision functions expect records that have already been converted with
`to_gl()` or `update_instances()`.

### Rectangle or texture against rectangles/textures

```python
from gl_utils import check_collision

hits = check_collision(sprites[0], rects, "rect")
```

The first argument is the rectangle-shaped object being tested. The second is
the obstacle list. Use either `"rect"` or `"tex"` for rectangle-shaped
obstacles. Rotated rectangle collision uses the separating axis theorem and
accounts for scale and aspect ratio.

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

### Mouse picking

Unlike other collision functions, `check_mouse_collisions()` accepts the mouse
position in pygame pixels and converts it internally:

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

- `point_in_rotated_rect(px, py, cx, cy, scale_x, scale_y, rotation)` returns a
  Boolean. Coordinates must be in clip space and rotation must be in radians.
- `get_rect_corners(cx, cy, scale_x, scale_y, rotation)` returns four clip-space
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

### `build_tex_objs(ctx, program, instances)`

Builds textured-quad geometry and returns `(vao, instance_vbo)`.

### `convert_to_clip_space(x, y)`

Converts pygame pixels to clip space using `WIDTH` and `HEIGHT`. Returns
`(clip_x, clip_y)`.

### `to_gl(data, instances, type_)`

Converts every populated record, copies it into `instances`, and returns
`(data, instances)`. This function mutates `data`.

### `update_instances(idx, data, instances, convert_xy=True, convert_rgb=True, convert_rot=True)`

Conditionally converts one record, copies it into `instances[idx]`, and returns
`instances`. This function does not write to the GPU.

### `load_texture(ctx, path)`

Loads an RGBA image and returns a nearest-filtered ModernGL texture.

### `check_collision(player, obstacles, type_)`

Returns typed obstacle-index tuples for all collisions with `player`.

### `check_mouse_collisions(mx, my, data, type_)`

Returns the indices of all objects containing the supplied mouse position.

## Common failure cases

- **Nothing is visible:** Confirm that the correct VAO is rendered with
  `instances=len(data)`, the object list is not empty, and `to_gl()` ran before
  the VAO was built.
- **Rectangles or sprites are stretched:** Set `u_aspect` and ensure the window
  size matches `WIDTH` and `HEIGHT`.
- **Points are the wrong size or invisible:** Enable
  `moderngl.PROGRAM_POINT_SIZE` and render with `vertices=1`.
- **An updated object jumps or changes color unexpectedly:** A previously
  converted field was converted again. Disable its `update_instances()` flag.
- **An update does not appear:** Writing to the Python list or NumPy array alone
  is insufficient. Upload the record with `vbo.write()`.
- **A buffer write fails or a new object is missing:** The object count may have
  exceeded the capacity passed to `get_new_instances()`.
- **A texture is black, white, or missing:** Bind it to the same unit assigned to
  `u_texture`, set `u_atlas_grid`, and verify the atlas tile coordinates.
- **Shader creation fails:** Custom shader attributes must exactly match the
  names and types required by the corresponding builder.
