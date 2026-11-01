// SPDX-License-Identifier: GPL-3.0-or-later
// Feasibility diagnostic only. Production shared sky/light/transparent transport is pending.
shader_type spatial;
render_mode unshaded, fog_disabled, cull_disabled, depth_draw_never;
uniform sampler2D scene_color : hint_screen_texture, filter_nearest;
uniform sampler2D scene_depth : hint_depth_texture, filter_nearest;
uniform vec3 physical_camera=vec3(0.0,6371002.0,7.0);
uniform float planet_radius=6371000.0;
void vertex(){ POSITION=vec4(VERTEX.xy,1.0,1.0); }
void fragment(){
    float depth=texture(scene_depth,SCREEN_UV).r;
    vec3 original=texture(scene_color,SCREEN_UV).rgb;
    ALBEDO=original;
    if(depth>0.000001){
        vec4 point=INV_PROJECTION_MATRIX*vec4(SCREEN_UV*2.0-1.0,depth,1.0);
        vec3 endpoint=point.xyz/point.w;
        float distance_m=length(endpoint);
        vec3 ray=normalize(mat3(INV_VIEW_MATRIX)*endpoint);
        float integral=0.0;
        for(int i=0;i<16;i++){
            vec3 p=physical_camera+ray*(float(i)+0.5)*distance_m/16.0;
            float altitude=max(length(p)-planet_radius,0.0);
            integral+=exp(-altitude/8000.0)*distance_m/16.0;
        }
        float transmittance=exp(-integral*0.00004);
        ALBEDO=original*transmittance+vec3(0.18,0.28,0.42)*(1.0-transmittance);
    }
}
