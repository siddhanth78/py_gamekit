#version 330

in vec3 v_color;
in vec2 v_uv;
in vec2 v_tile;
in float v_thickness;

out vec4 f_color;

uniform sampler2D u_texture;
uniform vec2 u_atlas_grid;

void main(){
    vec2 tile_size = 1.0 / u_atlas_grid;
    vec2 atlas_uv = (v_tile + v_uv) * tile_size;
    vec4 tex_color = texture(u_texture, atlas_uv);
    if (tex_color.a < 0.01) discard;
    f_color = tex_color * vec4(v_color, 1.0);
}