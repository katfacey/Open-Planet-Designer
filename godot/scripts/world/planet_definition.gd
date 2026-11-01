# SPDX-License-Identifier: GPL-3.0-or-later
extends Resource

@export var seed: int=42
@export var radius_m: float=6371000.0
@export var sea_level_m: float=0.0
@export var generator_revision: String="native-3"
@export var planet_id: String="open-planet-default"
@export var ecology_revision: String="earth-woodland-2"
var cache_namespace: String=""
@export var region_manifest: String="res://assets/native/regions.json"
@export var terrain_pixels: float=4.0
@export var max_depth: int=22
@export var leaf_budget: int=384
@export var resident_tile_limit: int=2048
@export var worker_limit: int=2
@export var upload_budget_ms: float=2.0
@export var disk_cache_mb: int=64
@export var tree_reach_m: float=600.0
@export var ground_reach_m: float=55.0
@export var tree_full_detail_m: float=12.0
@export var tree_medium_detail_m: float=95.0
@export var tree_impostor_start_m: float=180.0
@export var cover_full_detail_m: float=14.0
@export var cover_medium_detail_m: float=35.0
@export var shadow_distance_m: float=220.0
@export var scatter_triangle_budget: int=12000000
@export var instance_budget: int=30000

func signature() -> String:
	return ("%s/%s/%d/%.9f/%.9f" % [planet_id,generator_revision,seed,radius_m,sea_level_m]).sha256_text()
