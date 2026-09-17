#version 330

in vec2 in_position;
in vec4 in_color;

out vec4 v_color;

uniform vec2 u_viewport_size;

void main() {
    vec2 position = vec2(
        in_position.x / u_viewport_size.x * 2.0 - 1.0,
        1.0 - in_position.y / u_viewport_size.y * 2.0
    );
    gl_Position = vec4(position, 0.0, 1.0);
    v_color = in_color;
}
