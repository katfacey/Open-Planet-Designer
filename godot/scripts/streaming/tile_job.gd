# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
const TileMesh=preload("res://scripts/terrain/tile_mesh.gd")
var provider: RefCounted
var tile: Dictionary
var cache_path: String
var result: Dictionary={}
var cache_hit: bool=false
var corrupt_cache: bool=false
var worker_ms: float=0.0

func run() -> void:
	result={}; cache_hit=false; corrupt_cache=false
	var started := Time.get_ticks_usec()
	if FileAccess.file_exists(cache_path):
		var f := FileAccess.open(cache_path,FileAccess.READ)
		if f!=null and f.get_length()>=40 and f.get_buffer(4).get_string_from_ascii()=="OPD1":
			var size := f.get_32(); var checksum := f.get_buffer(32)
			if size==f.get_length()-40 and size<8388608:
				var payload := f.get_buffer(size)
				if digest(payload)==checksum:
					var decoded: Variant=bytes_to_var(payload)
					if decoded is Dictionary and decoded.get("tile",{}).get("key","")==tile.key:
						result=decoded; cache_hit=true
		if f!=null: f.close()
		corrupt_cache=result.is_empty()
	if result.is_empty():
		result=generate()
		var payload := var_to_bytes(result)
		var temporary := cache_path+".%d.%d.tmp" % [OS.get_process_id(),WorkerThreadPool.get_caller_task_id()]
		var f := FileAccess.open(temporary,FileAccess.WRITE)
		if f!=null:
			f.store_buffer("OPD1".to_ascii_buffer()); f.store_32(payload.size()); f.store_buffer(digest(payload)); f.store_buffer(payload); f.close()
			if FileAccess.file_exists(cache_path): DirAccess.remove_absolute(cache_path)
			DirAccess.rename_absolute(temporary,cache_path)
	worker_ms=(Time.get_ticks_usec()-started)/1000.0

func generate() -> Dictionary:
	return TileMesh.generate(provider,tile)

static func digest(payload: PackedByteArray) -> PackedByteArray:
	var context := HashingContext.new(); context.start(HashingContext.HASH_SHA256); context.update(payload)
	return context.finish()
