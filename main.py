import pygame
import moderngl
import numpy as np
from gl_utils import *

pygame.init()

pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
pygame.key.set_repeat(200, 50)

ctx = moderngl.create_context()
ctx.enable(moderngl.PROGRAM_POINT_SIZE)
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

print(f"GPU Hardware: {ctx.info['GL_RENDERER']}")
print(f"GPU Vendor:   {ctx.info['GL_VENDOR']}")
print(f"GL Version:   {ctx.info['GL_VERSION']}")

clock = pygame.time.Clock()

# Instances buffers
rn = 5000
pn = 5000
tn = 5000

running = True

program_rect = load_program(ctx, 'shaders/rect.vert', 'shaders/rect.frag')
program_point = load_program(ctx, 'shaders/point.vert', 'shaders/point.frag')
program_tex = load_program(ctx, 'shaders/tex.vert', 'shaders/tex.frag')

program_rect["u_aspect"] = aspect
program_tex["u_aspect"] = aspect

# x,y: pygame coords
# r,g,b,a: standard 0-255 range
# thickness: boundary thickness 0-1
# scale: scaling factor
# rotation: degrees
# tile: texture coord in atlas

# check scripts, gl_utils, and globals for defaults

#       [x,y,     r,g,b,a,         thickness, scale_x,scale_y, rotation]
all_rects = [
        [200,200, 255,255,255,255,  0.08,       0.5,0.5,          0],
        [300,300, 255,0,0,255,      1.0,        0.5,0.5,          0],
        [350,300, 255,0,0,255,      1.0,        0.5,0.5,          0]]


#             [x,y,     r,g,b,a,         scale]
all_points = [[150,150, 255,255,255,255, 1.0]]


#Player texture
#          [x,y,     r,g,b,a,        thickness(value doesn't matter just filler), scale_x,scale_y, rotation,   tile]
all_tex = [[32,32,     255,255,255,255,    0,                                          1.0,1.0,         0,       0,0]]

rect_instances, point_instances, tex_instances = get_new_instances(rn, pn, tn)

# Pointer set to modify tex instance
p_index = 0

# speed: movement speed
# px,py: pygame coords
speed = 10
px,py = all_tex[p_index][0], all_tex[p_index][1]

# Convert to gl format and populate instance arrays
all_rects, rect_instances = to_gl(all_rects, rect_instances, 'rect')
all_points, point_instances = to_gl(all_points, point_instances, 'point')
all_tex, tex_instances = to_gl(all_tex, tex_instances, 'tex')

# Load atlas textures
atlas_texture = load_texture(ctx, 'assets/character.png') #Uniform-sized atlas
atlas_texture.use(location=0) #GPU slot 0
program_tex['u_texture'] = 0
program_tex["u_atlas_grid"] = (1.0, 1.0) #atlas size

# Build rects and points vaos and vbos
rect_vao, rvbo = build_rect_objs(ctx, program_rect, rect_instances)
point_vao, pvbo = build_point_objs(ctx, program_point, point_instances)
tex_vao, tvbo = build_tex_objs(ctx, program_tex, tex_instances)

# Array of indices of collided objs (rect type and tex type collisions are interchangable due to structural similarities)
collisions = []
previous_collisions = set()
current_collisions = set()
mouse_collisions = []

dirty = False

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

            px = max(32, min(WIDTH-32, px))
            py = max(32, min(HEIGHT-32, py))

            if event.key in [pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s]:
                all_tex = modify_xy(p_index, all_tex, px, py)
                tex_instances = update_instances(p_index, all_tex, tex_instances, convert_rgba=False, convert_rot=False)
                tvbo.write(tex_instances[p_index].tobytes(), offset=p_index*tstride)

                previous_collisions = set(collisions)
                collisions = check_collision(all_tex[p_index], all_rects, 'rect') + check_collision(all_tex[p_index], all_points, 'point')
                current_collisions = set(collisions)

                for t,idx in current_collisions - previous_collisions:
                    if t == 'rt':
                        all_rects = modify_rgba(idx, all_rects, 255,0,255,255)
                        rect_instances = update_instances(idx, all_rects, rect_instances, convert_xy=False, convert_rot=False)
                        rvbo.write(rect_instances[idx].tobytes(), offset=idx*rstride)
                    elif t == 'p':
                        all_points = modify_rgba(idx, all_points, 255,0,255,255)
                        point_instances = update_instances(idx, all_points, point_instances, convert_xy=False, convert_rot=False)
                        pvbo.write(point_instances[idx].tobytes(), offset=idx*pstride)
                for t_,ar in previous_collisions - current_collisions:
                    if t_ == 'rt':
                        r,g,b = (255,255,255) if ar == 0 else (255, 0,0)
                        all_rects = modify_rgba(ar, all_rects, r,g,b,255)
                        rect_instances = update_instances(ar, all_rects, rect_instances, convert_xy=False, convert_rot=False)
                        rvbo.write(rect_instances[ar].tobytes(), offset=ar*rstride)
                    elif t_ == 'p':
                        r,g,b = (255,255,255)
                        all_points = modify_rgba(ar, all_points, r,g,b,255)
                        point_instances = update_instances(ar, all_points, point_instances, convert_xy=False, convert_rot=False)
                        pvbo.write(point_instances[ar].tobytes(), offset=ar*pstride)
                previous_collisions = current_collisions
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_collisions = check_mouse_collisions(mx,my,all_rects,'rect')
                if mouse_collisions:
                    idx = mouse_collisions[0]
                    all_rects = modify_rgba(idx, all_rects, 255,0,255,255)
                    rect_instances = update_instances(idx, all_rects, rect_instances, convert_xy=False, convert_rot=False)
                    rvbo.write(rect_instances[idx].tobytes(), offset=idx*rstride)
                else:
                    all_points.append([mx,my, 255,255,255,255, 1.0])
                    point_instances = update_instances(len(all_points)-1, all_points, point_instances, convert_rot=False)
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
    tex_vao.render(moderngl.TRIANGLES, instances=len(all_tex))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
