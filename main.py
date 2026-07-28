import pygame
import moderngl
import numpy as np
import math

pygame.init()

WIDTH, HEIGHT = 800, 600

pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
pygame.key.set_repeat(200, 50)

ctx = moderngl.create_context()
ctx.enable(moderngl.PROGRAM_POINT_SIZE)

print(f"GPU Hardware: {ctx.info['GL_RENDERER']}")
print(f"GPU Vendor:   {ctx.info['GL_VENDOR']}")
print(f"GL Version:   {ctx.info['GL_VERSION']}")

clock = pygame.time.Clock()

N=5000

aspect = WIDTH/HEIGHT

# Load rect shader
def load_rect_program(ctx, vert_path, frag_path):
    with open(vert_path, 'r') as vf:
        v_code = vf.read()
    with open(frag_path, 'r') as ff:
        f_code = ff.read()

    return ctx.program(
                vertex_shader = v_code,
                fragment_shader = f_code
            )

# Load point shader
def load_point_program(ctx, vert_path, frag_path):
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

# Convert pygame to gl coords
def convert_to_clip_space(x,y):
    cx = (x / WIDTH) * 2.0 - 1.0
    cy = 1.0 - (y / HEIGHT) * 2.0
    return cx, cy

# Update instance via index
def update_instances(idx, data, instances, convert_xy=True, convert_rgb=True):
    if convert_xy == True:
        data[idx][0], data[idx][1] = convert_to_clip_space(data[idx][0], data[idx][1])
    if convert_rgb == True:
        data[idx][2], data[idx][3], data[idx][4] = data[idx][2]/255.0, data[idx][3]/255.0, data[idx][4]/255.0
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

    if type_ == 'rect':
        player_corners = get_rect_corners(player[0], player[1], player[6], player[7], player[8])
        for o in range(len(obstacles)):
            obs_corners = get_rect_corners(obstacles[o][0], obstacles[o][1],
                                            obstacles[o][6], obstacles[o][7], obstacles[o][8])
            if sat_collision(player_corners, obs_corners):
                all_collided.append(o)

    elif type_ == 'point':
        for o in range(len(obstacles)):
            px, py = obstacles[o][0], obstacles[o][1]
            if point_in_rotated_rect(px, py, player[0], player[1], player[6], player[7], player[8]):
                all_collided.append(o)

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
        elif type_ == 'rect':
            if point_in_rotated_rect(mx, my, data[i][0], data[i][1], data[i][6], data[i][7], data[i][8]):
                all_collided.append(i)
    return all_collided

# Convert data to gl-expected format
# degrees -> rad (rects only)
# coords -> gl clip space coords
# rgb -> 0-1 norm
def to_gl(data, instances, type_):
    if type_ == 'rect':
        for i in range(len(data)):
            data[i][-1] = math.radians(data[i][-1])
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

running = True

program_rect = load_rect_program(ctx, 'shaders/rect.vert', 'shaders/rect.frag')
program_point = load_point_program(ctx, 'shaders/point.vert', 'shaders/point.frag')

program_rect["u_aspect"] = aspect

# 4 bytes x 9 floats (rects)
rstride = 4*9

# 4 bytes x 6 floats (points)
pstride = 4*6

# x,y: pygame coords
# r,g,b: standard 0-255 range
# thickness: boundary thickness 0-1
# scale: scaling factor
# rotation: degrees

# check scripts and globals for defaults

#       [x,y,     r,g,b,       thickness, scale_x,scale_y, rotation]
all_rects = [
        [0,0,     255,255,255,  0.08,       0.5,0.5,          0],   #player
        [300,300, 255,0,0,      1.0,        5.0,5.0,          0]]
rect_instances = np.zeros((N, 9), dtype='f4')

#             [x,y,     r,g,b,       scale]
all_points = [[150,150, 255,255,255, 1.0]]
point_instances = np.zeros((N, 6), dtype='f4')

# Convert to gl format and populate instance arrays
all_rects, rect_instances = to_gl(all_rects, rect_instances, 'rect')
all_points, point_instances = to_gl(all_points, point_instances, 'point')

# Build rects and points vaos and vbos
rect_vao, rvbo = build_rect_objs(ctx, program_rect, rect_instances)
point_vao, pvbo = build_point_objs(ctx, program_point, point_instances)

# Pointer set to modify rect instance
p_index = 0

# speed: movement speed
# px,py: pygame coords
speed = 10
px,py = 0,0

# Array of indices of collided objs
collided = []
mouse_collisions = []

while running:

    mx,my = pygame.mouse.get_pos()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_a:
                px -= speed
            elif event.key == pygame.K_d:
                px += speed
            elif event.key == pygame.K_w:
                py -= speed
            elif event.key == pygame.K_s:
                py += speed

            px = max(0, min(WIDTH, px))
            py = max(0, min(HEIGHT, py))

            if event.key in [pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s]:
                all_rects = modify_xy(p_index, all_rects, px, py)
                rect_instances = update_instances(p_index, all_rects, rect_instances, convert_rgb=False)
                rvbo.write(rect_instances[p_index].tobytes(), offset=p_index*rstride)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_collisions = check_mouse_collisions(mx,my,all_rects,'rect')
                if mouse_collisions:
                    idx = mouse_collisions[0]
                    all_rects = modify_rgb(idx, all_rects, 255,0,255)
                    rect_instances = update_instances(idx, all_rects, rect_instances, convert_xy=False)
                    rvbo.write(rect_instances[idx].tobytes(), offset=idx*rstride)
                else:
                    all_points.append([mx,my, 255,255,255, 1.0])
                    point_instances = update_instances(len(all_points)-1, all_points, point_instances)
                    pvbo.write(point_instances[len(all_points)-1].tobytes(), offset=(len(all_points)-1)*pstride)
            elif event.button == 3:
                mouse_collisions = check_mouse_collisions(mx,my,all_points,'point')
                if mouse_collisions:
                    mouse_collisions = mouse_collisions[::-1]
                    for m in mouse_collisions:
                        idx = m
                        lid = len(all_points)-1
                        if idx != lid:
                            all_points[idx] = all_points[lid]
                            point_instances[idx] = point_instances[lid]
                        all_points.pop()
                        pvbo.write(point_instances[idx].tobytes(), offset=idx*pstride)

    ctx.clear(0, 0, 0)
    
    rect_vao.render(moderngl.TRIANGLES, instances=len(all_rects))
    point_vao.render(moderngl.POINTS, vertices=1, instances=len(all_points))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
