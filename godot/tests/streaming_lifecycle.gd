# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
const Location=preload("res://scripts/world/planet_location.gd")
const Definition=preload("res://scripts/world/planet_definition.gd")
const Provider=preload("res://scripts/terrain/height_provider.gd")
const Terrain=preload("res://scripts/streaming/terrain_stream.gd")
const SlowJob=preload("res://tests/slow_tile_job.gd")
const Selector=preload("res://scripts/terrain/tile_selector.gd")

func _initialize() -> void:
	_run.call_deferred()

func _run() -> void:
	var definition := Definition.new(); definition.leaf_budget=24; definition.resident_tile_limit=64; definition.worker_limit=1; definition.disk_cache_mb=2
	definition.cache_namespace="lifecycle-"+str(Time.get_ticks_usec())
	var provider := Provider.new(); provider.configure(definition)
	var stream := Terrain.new(); stream.job_type=SlowJob; root.add_child(stream)
	var material := ShaderMaterial.new(); material.shader=load("res://shaders/native_ground.gdshader")
	stream.configure(provider,definition,material,"user://native-lifecycle-cache")
	var bounds_ok := true; var coverage_ok := true; var had_complete_coverage := false; var rebase_ok := true; var seams_ok := true
	for site in [[2,0.08,0.11],[0,0.05,0.3],[2,0.99999,0.03],[2,0.0,0.0],[2,0.08,0.11]]:
		var d := Location.direction(site[0],site[1],site[2]); var camera := Location.point(d,definition.radius_m+provider.height(d)+100.0)
		var origin := PackedFloat64Array([snappedf(camera[0],256.0),snappedf(camera[1],256.0),snappedf(camera[2],256.0)])
		stream.set_origin(origin); stream.force_selection()
		var deadline := Time.get_ticks_usec()+1500000
		while Time.get_ticks_usec()<deadline:
			stream.tick(0.016,camera,600.0)
			bounds_ok=bounds_ok and stream.resident.size()<=64 and stream.jobs.size()<=1 and stream.desired.size()<=24
			var areas := PackedFloat64Array([0,0,0,0,0,0])
			for tile in stream.active.values(): areas[tile.face]+=pow(0.25,float(tile.level))
			var complete := true
			for area in areas: complete=complete and absf(area-1.0)<1e-10
			for tile in stream.active.values():
				for edge in 4:
					var other := Selector.neighbour(tile,edge,stream.active)
					seams_ok=seams_ok and not other.is_empty() and absi(int(tile.level)-int(other.level))<=1
			if had_complete_coverage: coverage_ok=coverage_ok and complete
			had_complete_coverage=had_complete_coverage or complete
			for entry in stream.resident.values(): rebase_ok=rebase_ok and entry.node.position.distance_to(Location.local(entry.data.centre,origin))<0.00001
			await process_frame
	var checks := {"residency_workers_and_leaf_selection_bounded":bounds_ok,"complete_coarse_coverage_retained_during_travel":coverage_ok and had_complete_coverage,"active_boundaries_stay_2_to_1_during_delayed_loading":seams_ok,"all_resident_nodes_follow_rebase":rebase_ok,"obsolete_requests_discarded":stream.discarded>0,"travel_caused_eviction":stream.evictions>0,"return_route_loaded_from_cache":stream.cache_hits>0}
	var passed := true
	for value in checks.values(): passed=passed and bool(value)
	var report := {"checks":checks,"passed":passed,"statistics":stream.statistics()}
	var output := "user://native-lifecycle-checks.json"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="): output=arg.trim_prefix("--report=")
	var file := FileAccess.open(output,FileAccess.WRITE); file.store_string(JSON.stringify(report,"\t")); file.close()
	stream.shutdown(); stream.free()
	print("OPD_STREAM_LIFECYCLE ",JSON.stringify(report)); quit(0 if passed else 1)
