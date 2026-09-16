import math
from functools import lru_cache

import moderngl
import numpy as np
import pygame

WIDTH, HEIGHT = 800, 600
aspect = WIDTH/HEIGHT

# 4 bytes x 10 floats (rects)
rstride = 4*10

# 4 bytes x 7 floats (points)
pstride = 4*7

# 4 bytes x 12 floats (tex)
tstride = 4*12

# Empty instances
def get_new_instances(rn, pn, tn):
    rect_instances = np.zeros((rn, 10), dtype='f4')
    point_instances = np.zeros((pn, 7), dtype='f4')
    tex_instances = np.zeros((tn, 12), dtype='f4')

    return rect_instances, point_instances, tex_instances

# Load shader
def load_program(ctx, vert_path, frag_path):
    with open(vert_path, 'r') as vf:
        v_code = vf.read()
    with open(frag_path, 'r') as ff:
        f_code = ff.read()

    return ctx.program(
                vertex_shader = v_code,
                fragment_shader = f_code
            )

# Build rect instances
def build_rect_objs(ctx, program, instances):
    vertices = np.array([
        -0.1,-0.1,   0.0,0.0,
        0.1,-0.1,   1.0,0.0,
        0.1, 0.1,   1.0,1.0,
        -0.1, 0.1,   0.0,1.0
        ], dtype="f4")

    indices = np.array([
        0, 1, 2,
        0, 3, 2
        ], dtype="i4")

    quad_vbo = ctx.buffer(vertices.tobytes())
    quad_ibo = ctx.buffer(indices.tobytes())
    ivbo = ctx.buffer(instances.tobytes())

    vao = ctx.vertex_array(
            program,
            [(quad_vbo, '2f 2f', 'quad_position', 'quad_uv'),
             (ivbo, '2f 4f 1f 2f 1f /i', 'in_offset', 'in_color', 'in_thickness', 'in_scale', 'in_rotation')],
            index_buffer=quad_ibo
            )
    return vao, ivbo

# Build point instances
def build_point_objs(ctx, program, instances):
    ivbo = ctx.buffer(instances.tobytes())
    
    vao = ctx.vertex_array(
            program,
            [(ivbo, '2f 4f 1f /i', 'in_offset', 'in_color', 'in_scale')],
            )
    return vao, ivbo

# Convert pygame points and one RGBA color into interleaved line vertices
def create_line_vertices(points, rgba):
    if len(points) < 2:
        raise ValueError("A line requires at least two points")
    if len(rgba) != 4:
        raise ValueError("Line color must contain r, g, b, and a")

    color = np.asarray(rgba, dtype='f4') / 255.0
    vertices = np.empty((len(points), 6), dtype='f4')

    for i, (x, y) in enumerate(points):
        vertices[i][0], vertices[i][1] = convert_to_clip_space(x, y)
        vertices[i][2:6] = color

    return vertices

# Build a non-instanced line, line strip, or line loop
def build_line_obj(ctx, program, points, rgba):
    vertices = create_line_vertices(points, rgba)
    vbo = ctx.buffer(vertices.tobytes(), dynamic=True)
    vao = ctx.vertex_array(
            program,
            [(vbo, '2f 4f', 'in_position', 'in_color')],
            )
    return vao, vbo

# Replace line vertices without rebuilding the VAO
def update_line_obj(vbo, points, rgba):
    vertices = create_line_vertices(points, rgba)
    if vertices.nbytes > vbo.size:
        raise ValueError(
            "Updated line has more vertices than its buffer; rebuild it with "
            "build_line_obj()"
        )
    vbo.write(vertices.tobytes(), offset=0)
    return len(vertices)

def is_convex_polygon(points):
    if len(points) < 3 or len(set(map(tuple, points))) != len(points):
        return False

    epsilon = 1e-9

    def orientation(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0]))

    def on_segment(a, b, p):
        return (min(a[0], b[0]) - epsilon <= p[0] <= max(a[0], b[0]) + epsilon
                and min(a[1], b[1]) - epsilon <= p[1] <= max(a[1], b[1]) + epsilon)

    def segments_intersect(a, b, c, d):
        o1 = orientation(a, b, c)
        o2 = orientation(a, b, d)
        o3 = orientation(c, d, a)
        o4 = orientation(c, d, b)

        if ((o1 > epsilon and o2 < -epsilon) or (o1 < -epsilon and o2 > epsilon)) and ((o3 > epsilon and o4 < -epsilon) or (o3 < -epsilon and o4 > epsilon)):
            return True
        if abs(o1) <= epsilon and on_segment(a, b, c):
            return True
        if abs(o2) <= epsilon and on_segment(a, b, d):
            return True
        if abs(o3) <= epsilon and on_segment(c, d, a):
            return True
        if abs(o4) <= epsilon and on_segment(c, d, b):
            return True
        return False

    # Reject self-intersections between non-adjacent edges.
    count = len(points)
    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        for j in range(i + 1, count):
            if j == i or j == (i + 1) % count:
                continue
            if i == 0 and j == count - 1:
                continue
            c, d = points[j], points[(j + 1) % count]
            if segments_intersect(a, b, c, d):
                return False

    # Every non-collinear turn must have the same direction.
    turn_sign = 0
    for i in range(count):
        cross = orientation(
            points[i],
            points[(i + 1) % count],
            points[(i + 2) % count],
        )
        if abs(cross) <= epsilon:
            continue
        current_sign = 1 if cross > 0 else -1
        if turn_sign == 0:
            turn_sign = current_sign
        elif current_sign != turn_sign:
            return False

    return turn_sign != 0

def _relative_polygon_signature(points):
    if not points:
        return ()
    origin_x, origin_y = points[0]
    return tuple((x - origin_x, y - origin_y) for x, y in points)

@lru_cache(maxsize=256)
def _polygon_fill_is_valid(relative_points):
    return is_convex_polygon(relative_points)

# Build polygon vertices for outline or conditionally filled rendering
def build_polygon_obj(ctx, program, points, rgba):
    return build_line_obj(ctx, program, points, rgba)

# Replace polygon vertices without rebuilding the VAO
def update_polygon_obj(vbo, points, rgba):
    return update_line_obj(vbo, points, rgba)

# Fill valid convex polygons; otherwise fall back to an outline
def render_polygon(vao, points, fill=False):
    if len(points) < 2:
        raise ValueError("A polygon outline requires at least two points")
    filled = False
    if fill:
        relative_points = _relative_polygon_signature(points)
        filled = _polygon_fill_is_valid(relative_points)
    mode = moderngl.TRIANGLE_FAN if filled else moderngl.LINE_LOOP
    vao.render(mode, vertices=len(points))
    return filled

# Build tex instances
def build_tex_objs(ctx, program, instances):
    vertices = np.array([
        -0.1,-0.1,   0.0,0.0,
        0.1,-0.1,   1.0,0.0,
        0.1, 0.1,   1.0,1.0,
        -0.1, 0.1,   0.0,1.0
        ], dtype="f4")

    indices = np.array([
        0, 1, 2,
        0, 3, 2
        ], dtype="i4")

    quad_vbo = ctx.buffer(vertices.tobytes())
    quad_ibo = ctx.buffer(indices.tobytes())
    ivbo = ctx.buffer(instances.tobytes())

    vao = ctx.vertex_array(
            program,
            [(quad_vbo, '2f 2f', 'quad_position', 'quad_uv'),
             (ivbo, '2f 4f 1f 2f 1f 2f /i', 'in_offset', 'in_color', 'in_thickness', 'in_scale', 'in_rotation', 'in_tile')],
            index_buffer=quad_ibo
            )
    return vao, ivbo

# Convert pygame to gl coords
def convert_to_clip_space(x,y):
    cx = (x / WIDTH) * 2.0 - 1.0
    cy = 1.0 - (y / HEIGHT) * 2.0
    return cx, cy

# Update instance via index
def update_instances(idx, data, instances, convert_xy=True, convert_rgba=True, convert_rot=True):
    if convert_xy == True:
        data[idx][0], data[idx][1] = convert_to_clip_space(data[idx][0], data[idx][1])
    if convert_rgba == True:
        data[idx][2], data[idx][3], data[idx][4], data[idx][5] = data[idx][2]/255.0, data[idx][3]/255.0, data[idx][4]/255.0, data[idx][5]/255.0
    if convert_rot == True and len(data[idx]) > 9:
        data[idx][9] = math.radians(data[idx][9])
    instances[idx] = data[idx]
    return instances

# Point vs rotated rect (used by both collision checks below)
def point_in_rotated_rect(px, py, cx, cy, scale_x, scale_y, rotation):
    dx = (px - cx) * aspect
    dy = py - cy
    cos_a, sin_a = math.cos(rotation), math.sin(rotation)
    lx = dx * cos_a + dy * sin_a
    ly = -dx * sin_a + dy * cos_a
    hx, hy = 0.1 * scale_x, 0.1 * scale_y
    return abs(lx) <= hx and abs(ly) <= hy


# World-space corners of a rotated rect
def get_rect_corners(cx, cy, scale_x, scale_y, rotation):
    hx, hy = 0.1 * scale_x, 0.1 * scale_y
    local = [(-hx,-hy), (hx,-hy), (hx,hy), (-hx,hy)]
    cos_a, sin_a = math.cos(rotation), math.sin(rotation)
    corners = []
    for lx, ly in local:
        rx = lx*cos_a - ly*sin_a
        ry = lx*sin_a + ly*cos_a
        rx /= aspect
        corners.append((cx+rx, cy+ry))
    return corners


def _project(poly, axis):
    dots = [x*axis[0] + y*axis[1] for x, y in poly]
    return min(dots), max(dots)


def _overlap_on_axis(poly1, poly2, axis):
    min1, max1 = _project(poly1, axis)
    min2, max2 = _project(poly2, axis)
    return max1 >= min2 and max2 >= min1


def sat_collision(poly1, poly2):
    for poly in (poly1, poly2):
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i+1) % len(poly)]
            axis = (-(y2-y1), x2-x1)
            length = math.hypot(*axis)
            if length == 0:
                continue
            axis = (axis[0]/length, axis[1]/length)
            if not _overlap_on_axis(poly1, poly2, axis):
                return False
    return True


# Convex polygon vs convex polygon; points use pygame pixel coordinates
def check_convex_polygon_collision(poly1, poly2):
    if not is_convex_polygon(poly1) or not is_convex_polygon(poly2):
        raise ValueError("Polygons must be simple, non-degenerate, and convex")

    clip_poly1 = [convert_to_clip_space(x, y) for x, y in poly1]
    clip_poly2 = [convert_to_clip_space(x, y) for x, y in poly2]
    return sat_collision(clip_poly1, clip_poly2)


# Convex pygame-coordinate polygon vs converted rect/texture record
def check_convex_polygon_rect_collision(polygon, rect):
    if not is_convex_polygon(polygon):
        raise ValueError("Polygon must be simple, non-degenerate, and convex")

    clip_polygon = [convert_to_clip_space(x, y) for x, y in polygon]
    rect_corners = get_rect_corners(
        rect[0], rect[1], rect[7], rect[8], rect[9]
    )
    return sat_collision(clip_polygon, rect_corners)


# Check 2d collisions
def check_collision(player, obstacles, type_):
    all_collided = []

    if type_ in ['rect','tex']:
        player_corners = get_rect_corners(player[0], player[1], player[7], player[8], player[9])
        for o in range(len(obstacles)):
            obs_corners = get_rect_corners(obstacles[o][0], obstacles[o][1],
                                            obstacles[o][7], obstacles[o][8], obstacles[o][9])
            if sat_collision(player_corners, obs_corners):
                all_collided.append(('rt', o))

    elif type_ == 'point':
        for o in range(len(obstacles)):
            px, py = obstacles[o][0], obstacles[o][1]
            if point_in_rotated_rect(px, py, player[0], player[1], player[7], player[8], player[9]):
                all_collided.append(('p',o))

    return all_collided


def check_mouse_collisions(mx, my, data, type_):
    all_collided = []
    mx, my = convert_to_clip_space(mx, my)
    for i in range(len(data)):
        if type_ == 'point':
            half_p = 10*data[i][6]
            half_p_x = half_p * (2/WIDTH)
            half_p_y = half_p * (2/HEIGHT)
            if (data[i][0]-half_p_x <= mx <= data[i][0]+half_p_x) and (data[i][1]-half_p_y <= my <= data[i][1]+half_p_y):
                all_collided.append(i)
        elif type_ in ['rect','tex']:
            if point_in_rotated_rect(mx, my, data[i][0], data[i][1], data[i][7], data[i][8], data[i][9]):
                all_collided.append(i)
    return all_collided

# Convert data to gl-expected format
# degrees -> rad (rects only)
# coords -> gl clip space coords
# rgba -> 0-1 norm
def to_gl(data, instances, type_):
    if type_ in ['rect','tex']:
        for i in range(len(data)):
            data[i][9] = math.radians(data[i][9])
            data[i][0], data[i][1] = convert_to_clip_space(data[i][0], data[i][1])
            data[i][2], data[i][3], data[i][4], data[i][5] = data[i][2]/255.0, data[i][3]/255.0, data[i][4]/255.0, data[i][5]/255.0
            instances[i] = data[i]
    elif type_ == 'point':
        for j in range(len(data)):
            data[j][0], data[j][1] = convert_to_clip_space(data[j][0], data[j][1])
            data[j][2], data[j][3], data[j][4], data[j][5] = data[j][2]/255.0, data[j][3]/255.0, data[j][4]/255.0, data[j][5]/255.0
            instances[j] = data[j]

    return data, instances

def modify_xy(idx, data, x, y):
    data[idx][0], data[idx][1] = x,y
    return data

def modify_rgba(idx, data, r,g,b,a):
    data[idx][2],data[idx][3],data[idx][4],data[idx][5] = r,g,b,a
    return data

def modify_scale(idx, data, sx, sy, type_):
    if type_ in ['rect', 'tex']:
        data[idx][7],data[idx][8] = sx,sy
    elif type_ == 'point':
        data[idx][6] = sx
    return data

def modify_rot(idx, data, angle, type_='rect'):
    if type_ in ['rect', 'tex']:
        data[idx][9] = angle
    return data

def modify_thickness(idx, data, factor, type_='rect'):
    if type_ == 'rect':
        data[idx][6] = factor
    return data

def modify_texture(idx, data, tilex, tiley, type_='tex'):
    if type_ == 'tex':
        data[idx][10],data[idx][11] = tilex,tiley
    return data

def load_texture(ctx, path):
    surface = pygame.image.load(path).convert_alpha()
    #surface = pygame.transform.flip(surface, False, True)
    data = pygame.image.tobytes(surface, 'RGBA', True)
    texture = ctx.texture(surface.get_size(), 4, data)
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    return texture
