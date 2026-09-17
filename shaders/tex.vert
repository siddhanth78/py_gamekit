#version 330

in vec2 quad_position;
in vec2 in_offset;
in vec4 in_color;
in vec2 in_size;
in float in_rotation;
in float in_thickness;
in vec2 in_tile;
in vec2 quad_uv;

uniform vec2 u_viewport_size;

out vec4 v_color;
out vec2 v_uv;
out vec2 v_tile;
out float v_thickness;

vec2 rotate(vec2 qpos, float angle){
  float s = sin(angle);
  float c = cos(angle);
  return vec2(qpos.x*c - qpos.y*s, qpos.x*s + qpos.y*c);
  }

void main(){
    v_color = in_color;
    v_uv = quad_uv;
    v_tile = in_tile;
    v_thickness = in_thickness;
    vec2 center = vec2(
      in_offset.x / u_viewport_size.x * 2.0 - 1.0,
      1.0 - in_offset.y / u_viewport_size.y * 2.0
    );
    vec2 local_pixels = rotate(quad_position * in_size, in_rotation);
    vec2 local_clip = local_pixels * (2.0 / u_viewport_size);
    gl_Position = vec4(center + local_clip, 0.0, 1.0);
  }
