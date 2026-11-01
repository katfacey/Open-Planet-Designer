# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
const Provider=preload("res://scripts/terrain/height_provider.gd")
const Definition=preload("res://scripts/world/planet_definition.gd")
const Location=preload("res://scripts/world/planet_location.gd")
func _initialize() -> void:
	var provider := Provider.new(); provider.configure(Definition.new())
	var best := {}; var score := -INF
	for x in range(-8,9):
		for y in range(-8,9):
			var u := 0.08+x*0.000025; var v := 0.11+y*0.000025
			var field := provider.sample(Location.direction(2,u,v))
			if field[4]>score and field[0]>10.0:
				score=field[4]; best={"face":2,"u":u,"v":v,"height":field[0],"forest":field[4]}
	print("WOODLAND_CANDIDATE ",JSON.stringify(best)); quit()
