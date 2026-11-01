# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
## Delete only our typed cache files, including old provider revisions.
var root_folder: String
var limit: int
var result_bytes: int=0

func run() -> void:
	result_bytes=prune(root_folder,limit)

static func prune(root: String,limit_bytes: int) -> int:
	var files := []; var bytes := _collect(root,files,0)
	files.sort_custom(func(a: Dictionary,b: Dictionary): return a.time<b.time)
	for file in files:
		if bytes<=limit_bytes: break
		if DirAccess.remove_absolute(file.path)==OK: bytes-=int(file.bytes)
	return bytes

static func _collect(root: String,files: Array,depth: int) -> int:
	var total := 0
	for filename in DirAccess.get_files_at(root):
		var path := root+"/"+filename
		var modified := FileAccess.get_modified_time(path)
		if not filename.ends_with(".opdc") and not (filename.ends_with(".tmp") and Time.get_unix_time_from_system()-modified>600.0): continue
		var file := FileAccess.open(path,FileAccess.READ)
		if file==null: continue
		var size := file.get_length(); file.close(); total+=size
		files.append({"path":path,"bytes":size,"time":modified})
	if depth<2:
		for folder in DirAccess.get_directories_at(root):
			var hash_directory := folder.length()==64 and folder.is_valid_hex_number(false)
			if hash_directory or folder in ["patch-1","cells-1","cells-2"]: total+=_collect(root+"/"+folder,files,depth+1)
	return total
