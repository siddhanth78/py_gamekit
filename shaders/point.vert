#version 330

in vec2 in_offset;
in vec3 in_color;
in float in_scale;

out vec3 v_color;

void main(){
    v_color = in_color;
    gl_Position = vec4(in_offset, 0.0, 1.0);
    gl_PointSize = in_scale*20;
  }
