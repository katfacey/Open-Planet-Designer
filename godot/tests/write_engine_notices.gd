# SPDX-License-Identifier: GPL-3.0-or-later
extends SceneTree
func _initialize() -> void:
	var destination := "user://GODOT_NOTICES.txt"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="): destination=arg.trim_prefix("--output=")
	var text: String="Godot "+str(Engine.get_version_info().string)+"\n\n"+Engine.get_license_text()+"\n\nCOMPILED COMPONENT COPYRIGHT INFORMATION\n"
	for item in Engine.get_copyright_info(): text+="\n"+str(item.name)+"\n"+JSON.stringify(item.parts,"  ")+"\n"
	text+="\nLICENSE TEXTS\n"
	var licenses := Engine.get_license_info()
	for key in licenses: text+="\n"+str(key)+"\n"+str(licenses[key])+"\n"
	var file := FileAccess.open(destination,FileAccess.WRITE); file.store_string(text); file.close(); quit()
