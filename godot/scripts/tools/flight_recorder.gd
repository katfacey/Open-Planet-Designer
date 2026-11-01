# SPDX-License-Identifier: GPL-3.0-or-later
extends RefCounted
var samples: Array=[]
var start_us: int=Time.get_ticks_usec()
var previous_us: int=0
var peaks: Dictionary={}
var render_size := Vector2i.ZERO
var timeline_time: float=-1.0
var frame_columns: Dictionary={"frame_ms":PackedFloat32Array(),"gpu_ms":PackedFloat32Array(),"render_cpu_ms":PackedFloat32Array(),"runtime_update_ms":PackedFloat32Array(),"upload_and_retire_ms":PackedFloat32Array(),"selection_worker_ms":PackedFloat32Array(),"ecology_upload_ms":PackedFloat32Array()}
var dropped_frames: int=0

func sample(viewport: Viewport,stream: Dictionary,extra: Dictionary) -> void:
	# Root ViewportTexture.get_size() can include desktop scaling a second time.
	# Window.size matches the actual readback image on the pinned Windows build.
	render_size=viewport.size if viewport is Window else Vector2i(viewport.get_texture().get_size())
	var now := Time.get_ticks_usec()
	var record := {"time_s":(now-start_us)/1000000.0,"frame_ms":(now-previous_us)/1000.0 if previous_us>0 else 0.0,
		"gpu_ms":RenderingServer.viewport_get_measured_render_time_gpu(viewport.get_viewport_rid()),
		"render_cpu_ms":RenderingServer.viewport_get_measured_render_time_cpu(viewport.get_viewport_rid())+RenderingServer.get_frame_setup_time_cpu(),
		"engine_static_bytes":Performance.get_monitor(Performance.MEMORY_STATIC),
		"render_texture_bytes":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED),
		"render_buffer_bytes":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_BUFFER_MEM_USED),
		"draw_calls":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"submitted_primitives":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}
	record.merge(stream); record.merge(extra); previous_us=now
	for key in record:
		if record[key] is float or record[key] is int: peaks[key]=maxf(float(peaks.get(key,0.0)),float(record[key]))
	if extra.get("phase","")=="flight":
		if frame_columns.frame_ms.size()<180000:
			for key in frame_columns: frame_columns[key].append(float(record.get(key,0.0)))
		else: dropped_frames+=1
	# Bounded 5 Hz timeline retains the entire route, rather than only its first frames.
	if float(record.time_s)-timeline_time>=0.2:
		if samples.size()<18000: samples.append(record)
		timeline_time=record.time_s

func report(path: String,metadata: Dictionary) -> void:
	var distributions := {}
	for key in ["frame_ms","gpu_ms","render_cpu_ms","runtime_update_ms","upload_and_retire_ms","selection_worker_ms","ecology_upload_ms"]:
		var values: PackedFloat32Array=frame_columns[key].duplicate()
		values.sort()
		if not values.is_empty(): distributions[key]={"p50":values[values.size()/2],"p95":values[mini(values.size()-1,int(ceil(values.size()*0.95))-1)],"p99":values[mini(values.size()-1,int(ceil(values.size()*0.99))-1)]}
	var result := {"schema":2,"engine":Engine.get_version_info(),"gpu":RenderingServer.get_video_adapter_name(),
		"driver":RenderingServer.get_current_rendering_driver_name(),"renderer":RenderingServer.get_current_rendering_method(),
		"resolution":[render_size.x,render_size.y],"duration_s":(Time.get_ticks_usec()-start_us)/1000000.0,
		"samples":samples,"peaks":peaks,"flight_distributions":distributions,
		"flight_frame_count":frame_columns.frame_ms.size(),"dropped_frames":dropped_frames,"timeline_interval_s":0.2,
		"memory_scope":"RenderingServer counters are estimates, engine_static is not process RSS or total driver VRAM. Harness records process memory separately.",
		"metadata":metadata}
	var file := FileAccess.open(path,FileAccess.WRITE)
	if file==null: push_error("Cannot write profiling report: "+path); return
	file.store_string(JSON.stringify(result,"\t")); file.close()
	var raw := FileAccess.open(path+".frames",FileAccess.WRITE)
	var header := JSON.stringify({"columns":frame_columns.keys(),"frames":frame_columns.frame_ms.size(),"encoding":"column-major little-endian float32"}).to_utf8_buffer()
	raw.store_buffer("OPDF".to_ascii_buffer()); raw.store_32(header.size()); raw.store_buffer(header)
	for key in frame_columns: raw.store_buffer(frame_columns[key].to_byte_array())
	raw.close()
	print("OPD_PROFILE_WRITTEN ",path)
