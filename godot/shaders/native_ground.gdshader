// SPDX-License-Identifier: GPL-3.0-or-later
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D meadow_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D litter_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D mud_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D meadow_rough : filter_linear_mipmap, repeat_enable;
uniform sampler2D litter_rough : filter_linear_mipmap, repeat_enable;
uniform sampler2D mud_rough : filter_linear_mipmap, repeat_enable;
uniform sampler2D rock_rough : filter_linear_mipmap, repeat_enable;
uniform sampler2D meadow_height : filter_linear_mipmap, repeat_enable;
uniform sampler2D litter_height : filter_linear_mipmap, repeat_enable;
uniform sampler2D mud_height : filter_linear_mipmap, repeat_enable;
uniform sampler2D rock_height : filter_linear_mipmap, repeat_enable;
uniform float moisture : hint_range(0.0,1.0)=0.35;
uniform bool alpine=false;
uniform float contact_range=100.0;
instance uniform float terrain_morph=0.0;
varying float slope;
varying float camera_distance;

void vertex(){
    float original_distance=length((MODELVIEW_MATRIX*vec4(VERTEX,1.0)).xyz);
    VERTEX+=CUSTOM0.xyz*terrain_morph*smoothstep(contact_range,contact_range*1.5,original_distance);
    slope=clamp(CUSTOM0.w,0.0,1.0);
    camera_distance=length((MODELVIEW_MATRIX*vec4(VERTEX,1.0)).xyz);
}

void fragment(){
    float land=clamp(COLOR.r,0.0,1.0);
    float forest=clamp(COLOR.g,0.0,1.0);
    float desert=clamp(COLOR.a,0.0,1.0);
    float rock=max(1.0-smoothstep(0.57,0.88,slope),max(COLOR.b*0.52,desert*0.38));
    float wet=moisture*smoothstep(0.65,0.96,slope)*(1.0-desert*0.9);
    vec4 weights=vec4((1.0-rock)*(1.0-wet)*(1.0-forest),(1.0-rock)*(1.0-wet)*forest,(1.0-rock)*wet,rock);
    vec2 mud_uv=UV*(2.0/1.3), rock_uv=UV*(2.0/1.8);
    vec3 soil=texture(meadow_color,UV).rgb*weights.x+texture(litter_color,UV).rgb*weights.y
        +texture(mud_color,mud_uv).rgb*weights.z+texture(rock_color,rock_uv).rgb*weights.w;
    soil*=1.0-wet*0.28;
    vec3 macro=mix(vec3(0.075,0.12,0.035),vec3(0.025,0.065,0.018),forest);
    macro=mix(macro,vec3(0.28,0.17,0.08),desert);
    macro=mix(macro,vec3(0.18,0.17,0.15),rock);
    float detail=1.0-smoothstep(200.0,2000.0,camera_distance);
    vec3 color=mix(macro,soil,detail);
    if(alpine){color=mix(color,vec3(0.75,0.81,0.85),smoothstep(0.18,0.65,COLOR.b)*smoothstep(0.3,0.8,slope));}
    float rough=texture(meadow_rough,UV).r*weights.x+texture(litter_rough,UV).r*weights.y
        +texture(mud_rough,mud_uv).r*weights.z+texture(rock_rough,rock_uv).r*weights.w;
    ALBEDO=mix(vec3(0.006,0.025,0.045),color,smoothstep(0.4,0.6,land));
    ROUGHNESS=mix(0.16,clamp(rough*(1.0-wet*0.4),0.18,0.95),smoothstep(0.4,0.6,land));
    SPECULAR=0.5;
    // Surface shape and waves are exported geometry. Height maps add close microdetail.
    float h=texture(meadow_height,UV).r*weights.x+texture(litter_height,UV).r*weights.y
        +texture(mud_height,mud_uv).r*weights.z+texture(rock_height,rock_uv).r*weights.w;
    vec3 n=NORMAL;
    vec3 p_dx=dFdx(VERTEX),p_dy=dFdy(VERTEX);
    vec3 r1=cross(p_dy,n),r2=cross(n,p_dx);
    float determinant=dot(p_dx,r1);
    if(abs(determinant)>0.0000001){
        vec3 gradient=(r1*dFdx(h)+r2*dFdy(h))/determinant;
        NORMAL=normalize(n-gradient*0.012*detail*land);
    }
}
