# SPDX-License-Identifier: GPL-3.0-or-later
extends Resource
## Appearance is independent of canonical height and ecological identity.
@export var title: String="Earth · Natural woodland"
@export var sun_energy: float=1.7
@export var sky_energy: float=0.65
@export var exposure: float=1.0
@export var warmth: float=0.12
@export var camera_fov: float=50.0
@export var ground_moisture: float=0.18
@export var fog_density: float=0.0012
@export var foliage_backlight: float=0.22
@export var ssil: bool=true

func apply(environment: Environment,sun: DirectionalLight3D,camera: Camera3D,variant: String="woodland") -> void:
	var stylized := variant!="natural"
	var sky := Sky.new()
	if ResourceLoader.exists("res://assets/appearance/earth_daylight.hdr"):
		var panorama := PanoramaSkyMaterial.new()
		panorama.panorama=load("res://assets/appearance/earth_daylight.hdr")
		sky.sky_material=panorama
	else: sky.sky_material=PhysicalSkyMaterial.new()
	environment.sky=sky; environment.background_mode=Environment.BG_SKY
	environment.background_energy_multiplier=sky_energy
	environment.ambient_light_source=Environment.AMBIENT_SOURCE_SKY
	environment.ambient_light_energy=0.35
	environment.tonemap_mode=Environment.TONE_MAPPER_AGX
	environment.tonemap_exposure=exposure
	environment.adjustment_enabled=stylized
	environment.adjustment_saturation=1.025
	environment.adjustment_contrast=1.015
	environment.ssao_enabled=true; environment.ssao_radius=0.8; environment.ssao_intensity=0.65
	environment.ssil_enabled=ssil; environment.ssil_radius=2.0; environment.ssil_intensity=0.7
	environment.sdfgi_enabled=false
	environment.fog_enabled=true; environment.fog_density=fog_density
	environment.fog_light_color=Color(0.46,0.57,0.61)
	environment.fog_light_energy=0.65; environment.fog_sun_scatter=0.15
	environment.fog_sky_affect=0.0
	sun.light_energy=sun_energy
	sun.light_color=Color.WHITE.lerp(Color(1.0,0.86,0.67),warmth if stylized else 0.08)
	sun.light_angular_distance=0.7
	camera.fov=camera_fov

func prepare_material(source: Material,kind: String) -> Material:
	if not source is StandardMaterial3D: return source
	var material := source.duplicate() as StandardMaterial3D
	material.texture_filter=BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.metallic=0.0
	if kind=="GRASS": material.vertex_color_use_as_albedo=true
	if material.transparency!=BaseMaterial3D.TRANSPARENCY_DISABLED:
		material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		material.alpha_scissor_threshold=0.3
		material.cull_mode=BaseMaterial3D.CULL_DISABLED
		material.alpha_antialiasing_mode=BaseMaterial3D.ALPHA_ANTIALIASING_ALPHA_TO_COVERAGE
		material.alpha_antialiasing_edge=0.3
		material.backlight_enabled=true
		material.backlight=Color(0.6,0.72,0.4)*foliage_backlight
		material.metallic_specular=0.25
		material.roughness=maxf(material.roughness,0.78)
	return material

func ground_material(reference: bool=false) -> ShaderMaterial:
	var material := ShaderMaterial.new(); material.shader=load("res://shaders/native_ground.gdshader")
	for pair in [["meadow","leafy_grass"],["litter","forrest_ground_01"],["mud","brown_mud_leaves_01"],["rock","rock_boulder_dry"]]:
		for channel in ["color","roughness","height"]:
			var path: String="res://assets/catalog/scans/"+pair[1]+"_"+channel+(".jpg" if channel=="color" else ".png")
			if ResourceLoader.exists(path): material.set_shader_parameter(pair[0]+"_"+("rough" if channel=="roughness" else channel),load(path))
		var normal_path: String="res://assets/appearance/"+pair[1]+"_normal.png"
		if ResourceLoader.exists(normal_path): material.set_shader_parameter(pair[0]+"_normal",load(normal_path))
	material.set_shader_parameter("moisture",ground_moisture)
	material.set_shader_parameter("reference_mesh",reference)
	if ResourceLoader.exists("res://assets/appearance/forrest_ground_03_color.jpg"):
		for channel in ["color","normal","height","roughness","ao"]:
			var extension: String=".png" if channel in ["height","normal"] else ".jpg"
			var suffix: String="rough" if channel=="roughness" else channel
			material.set_shader_parameter("litter_"+suffix,load("res://assets/appearance/forrest_ground_03_"+channel+extension))
			material.set_shader_parameter("moss_"+suffix,load("res://assets/appearance/forest_leaves_02_"+channel+extension))
	return material
