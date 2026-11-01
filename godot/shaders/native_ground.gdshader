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
uniform sampler2D meadow_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D litter_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D mud_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D moss_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D moss_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D moss_rough : filter_linear_mipmap, repeat_enable;
uniform sampler2D moss_height : filter_linear_mipmap, repeat_enable;
uniform sampler2D moss_ao : filter_linear_mipmap, repeat_enable;
uniform sampler2D litter_ao : filter_linear_mipmap, repeat_enable;
uniform bool reference_mesh=false;
uniform float moisture : hint_range(0.0,1.0)=0.35;
uniform bool alpine=false;
uniform float contact_range=100.0;
instance uniform float terrain_morph=0.0;
varying float slope;
varying float camera_distance;

vec3 decode_normal(vec3 encoded){
    vec2 xy=encoded.xy*2.0-1.0;
    return normalize(vec3(xy,sqrt(max(0.001,1.0-dot(xy,xy)))));
}

void vertex(){
    float original_distance=length((MODELVIEW_MATRIX*vec4(VERTEX,1.0)).xyz);
    VERTEX+=CUSTOM0.xyz*terrain_morph*smoothstep(contact_range,contact_range*1.5,original_distance);
    slope=reference_mesh?clamp(dot(NORMAL,vec3(0.0,1.0,0.0)),0.0,1.0):clamp(CUSTOM0.w,0.0,1.0);
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
    vec2 moss_uv=UV*(2.0/3.0);
    float patch=0.5+0.25*sin(UV.x*0.483321947)+0.25*sin(UV.y*0.698131701);
    float moss=forest*smoothstep(0.25,0.75,patch)*0.65;
    vec3 litter=mix(texture(litter_color,UV).rgb,texture(moss_color,moss_uv).rgb,moss);
    vec3 soil=texture(meadow_color,UV).rgb*weights.x+litter*weights.y
        +texture(mud_color,mud_uv).rgb*weights.z+texture(rock_color,rock_uv).rgb*weights.w;
    soil*=1.0-wet*0.28;
    vec3 macro=mix(vec3(0.075,0.12,0.035),vec3(0.025,0.065,0.018),forest);
    macro=mix(macro,vec3(0.28,0.17,0.08),desert);
    macro=mix(macro,vec3(0.18,0.17,0.15),rock);
    float detail=1.0-smoothstep(200.0,2000.0,camera_distance);
    vec3 color=mix(macro,soil,detail);
    if(alpine){color=mix(color,vec3(0.75,0.81,0.85),smoothstep(0.18,0.65,COLOR.b)*smoothstep(0.3,0.8,slope));}
    float rough=texture(meadow_rough,UV).r*weights.x+mix(texture(litter_rough,UV).r,texture(moss_rough,moss_uv).r,moss)*weights.y
        +texture(mud_rough,mud_uv).r*weights.z+texture(rock_rough,rock_uv).r*weights.w;
    ALBEDO=mix(vec3(0.006,0.025,0.045),color,smoothstep(0.4,0.6,land));
    ROUGHNESS=mix(0.16,clamp(rough*(1.0-wet*0.4),0.18,0.95),smoothstep(0.4,0.6,land));
    SPECULAR=0.5;
    AO=mix(1.0,mix(texture(litter_ao,UV).r,texture(moss_ao,moss_uv).r,moss),weights.y);
    // Surface shape and waves are exported geometry. Height maps add close microdetail.
    float h=texture(meadow_height,UV).r*weights.x+mix(texture(litter_height,UV).r,texture(moss_height,moss_uv).r,moss)*weights.y
        +texture(mud_height,mud_uv).r*weights.z+texture(rock_height,rock_uv).r*weights.w;
    vec3 n=NORMAL;
    vec3 map_normal=decode_normal(texture(meadow_normal,UV).xyz)*weights.x
        +mix(decode_normal(texture(litter_normal,UV).xyz),decode_normal(texture(moss_normal,moss_uv).xyz),moss)*weights.y
        +decode_normal(texture(mud_normal,mud_uv).xyz)*weights.z+decode_normal(texture(rock_normal,rock_uv).xyz)*weights.w;
    vec3 dp1=dFdx(VERTEX),dp2=dFdy(VERTEX);
    vec2 duv1=dFdx(UV),duv2=dFdy(UV);
    vec3 p2=cross(dp2,n),p1=cross(n,dp1);
    vec3 t=p2*duv1.x+p1*duv2.x,b=p2*duv1.y+p1*duv2.y;
    float inv_scale=inversesqrt(max(max(dot(t,t),dot(b,b)),0.00000001));
    map_normal=normalize(mix(vec3(0.0,0.0,1.0),map_normal,0.8*detail));
    NORMAL=normalize(mat3(t*inv_scale,b*inv_scale,n)*map_normal);
    n=NORMAL;
    vec3 p_dx=dFdx(VERTEX),p_dy=dFdy(VERTEX);
    vec3 r1=cross(p_dy,n),r2=cross(n,p_dx);
    float determinant=dot(p_dx,r1);
    if(abs(determinant)>0.0000001){
        vec3 gradient=(r1*dFdx(h)+r2*dFdy(h))/determinant;
        NORMAL=normalize(n-gradient*0.012*detail*land);
    }
}
