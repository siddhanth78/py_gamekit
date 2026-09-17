#version 330

in vec2 in_offset;
in vec4 in_color;
in float in_size;

uniform vec2 u_viewport_size;

out vec4 v_color;

void main(){
    v_color = in_color;
    vec2 position = vec2(
      in_offset.x / u_viewport_size.x * 2.0 - 1.0,
      1.0 - in_offset.y / u_viewport_size.y * 2.0
    );
    gl_Position = vec4(position, 0.0, 1.0);
    gl_PointSize = in_size;
  }
