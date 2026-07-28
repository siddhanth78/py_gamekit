import math
import moderngl
import numpy as np
import pygame

WIDTH, HEIGHT = 800, 600
aspect = WIDTH/HEIGHT

# 4 bytes x 9 floats (rects)
rstride = 4*9

# 4 bytes x 6 floats (points)
pstride = 4*6

# 4 bytes x 11 floats (tex)
tstride = 4*11

# Empty instances
def get_new_instances(rn, pn, tn):
    rect_instances = np.zeros((rn, 9), dtype='f4')
    point_instances = np.zeros((pn, 6), dtype='f4')
    tex_instances = np.zeros((tn, 11), dtype='f4')

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
             (ivbo, '2f 3f 1f 2f 1f /i', 'in_offset', 'in_color', 'in_thickness', 'in_scale', 'in_rotation')],
            index_buffer=quad_ibo
            )
    return vao, ivbo

# Build point instances
def build_point_objs(ctx, program, instances):
    ivbo = ctx.buffer(instances.tobytes())
    
    vao = ctx.vertex_array(
            program,
            [(ivbo, '2f 3f 1f /i', 'in_offset', 'in_color', 'in_scale')],
            )
    return vao, ivbo

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
             (ivbo, '2f 3f 1f 2f 1f 2f /i', 'in_offset', 'in_color', 'in_thickness', 'in_scale', 'in_rotation', 'in_tile')],
            index_buffer=quad_ibo
            )
    return vao, ivbo

# Convert pygame to gl coords
def convert_to_clip_space(x,y):
    cx = (x / WIDTH) * 2.0 - 1.0
    cy = 1.0 - (y / HEIGHT) * 2.0
    return cx, cy

# Update instance via index
def update_instances(idx, data, instances, convert_xy=True, convert_rgb=True, convert_rot=True):
    if convert_xy == True:
        data[idx][0], data[idx][1] = convert_to_clip_space(data[idx][0], data[idx][1])
    if convert_rgb == True:
        data[idx][2], data[idx][3], data[idx][4] = data[idx][2]/255.0, data[idx][3]/255.0, data[idx][4]/255.0
    if convert_rot == True and len(data[idx]) > 6:
        data[idx][8] = math.radians(data[idx][8])
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


# Check 2d collisions
def check_collision(player, obstacles, type_):
    all_collided = []

    if type_ in ['rect','tex']:
        player_corners = get_rect_corners(player[0], player[1], player[6], player[7], player[8])
        for o in range(len(obstacles)):
            obs_corners = get_rect_corners(obstacles[o][0], obstacles[o][1],
                                            obstacles[o][6], obstacles[o][7], obstacles[o][8])
            if sat_collision(player_corners, obs_corners):
                all_collided.append(('rt', o))

    elif type_ == 'point':
        for o in range(len(obstacles)):
            px, py = obstacles[o][0], obstacles[o][1]
            if point_in_rotated_rect(px, py, player[0], player[1], player[6], player[7], player[8]):
                all_collided.append(('p',o))

    return all_collided


def check_mouse_collisions(mx, my, data, type_):
    all_collided = []
    mx, my = convert_to_clip_space(mx, my)
    for i in range(len(data)):
        if type_ == 'point':
            half_p = 10*data[i][5]
            half_p_x = half_p * (2/WIDTH)
            half_p_y = half_p * (2/HEIGHT)
            if (data[i][0]-half_p_x <= mx <= data[i][0]+half_p_x) and (data[i][1]-half_p_y <= my <= data[i][1]+half_p_y):
                all_collided.append(i)
        elif type_ in ['rect','tex']:
            if point_in_rotated_rect(mx, my, data[i][0], data[i][1], data[i][6], data[i][7], data[i][8]):
                all_collided.append(i)
    return all_collided

# Convert data to gl-expected format
# degrees -> rad (rects only)
# coords -> gl clip space coords
# rgb -> 0-1 norm
def to_gl(data, instances, type_):
    if type_ in ['rect','tex']:
        for i in range(len(data)):
            data[i][8] = math.radians(data[i][8])
            data[i][0], data[i][1] = convert_to_clip_space(data[i][0], data[i][1])
            data[i][2], data[i][3], data[i][4] = data[i][2]/255.0, data[i][3]/255.0, data[i][4]/255.0
            instances[i] = data[i]
    elif type_ == 'point':
        for j in range(len(data)):
            data[j][0], data[j][1] = convert_to_clip_space(data[j][0], data[j][1])
            data[j][2], data[j][3], data[j][4] = data[j][2]/255.0, data[j][3]/255.0, data[j][4]/255.0
            instances[j] = data[j]

    return data, instances

def modify_xy(idx, data, x, y):
    data[idx][0], data[idx][1] = x,y
    return data

def modify_rgb(idx, data, r,g,b):
    data[idx][2],data[idx][3],data[idx][4] = r,g,b
    return data

def modify_scale(idx, data, sx, sy, type_):
    if type_ in ['rect', 'tex']:
        data[idx][6],data[idx][7] = sx,sy
    elif type_ == 'point':
        data[idx][5] = sx
    return data

def modify_rot(idx, data, angle, type_='rect'):
    if type_ in ['rect', 'tex']:
        data[idx][8] = angle
    return data

def modify_thickness(idx, data, factor, type_='rect'):
    if type_ == 'rect':
        data[idx][5] = factor
    return data

def modify_texture(idx, data, tilex, tiley, type_='tex'):
    if type_ == 'tex':
        data[idx][9],data[idx][10] = tilex,tiley
    return data

def load_texture(ctx, path):
    surface = pygame.image.load(path).convert_alpha()
    #surface = pygame.transform.flip(surface, False, True)
    data = pygame.image.tobytes(surface, 'RGBA', True)
    texture = ctx.texture(surface.get_size(), 4, data)
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    return texture