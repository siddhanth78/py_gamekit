#version 330

in vec2 quad_position;
in vec2 in_offset;
in vec4 in_color;
in vec2 in_scale;
in float in_rotation;
in float in_thickness;
in vec2 in_tile;
in vec2 quad_uv;

uniform float u_aspect;

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
    vec2 scaled = rotate(quad_position * in_scale, in_rotation);
    scaled.x /= u_aspect;
    gl_Position = vec4(scaled + in_offset, 0.0, 1.0);
  }
