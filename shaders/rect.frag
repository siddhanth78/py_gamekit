#version 330

in vec4 v_color;
in vec2 v_uv;
in float v_thickness;

out vec4 f_color;

void main(){
    float t = v_thickness;

    if (t > 0.0){
      bool isEdge = v_uv.x < t || v_uv.x > 1.0-t || v_uv.y < t || v_uv.y > 1.0-t;

      if (!isEdge) {
        discard;
      }
    }
    
    f_color = v_color;
      
  }
