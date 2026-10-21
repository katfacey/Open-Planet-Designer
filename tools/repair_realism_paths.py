"""Bake the review's existing entry paths above its revised canonical terrain."""
import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import open_planet_lab;open_planet_lab.register()
from open_planet_lab import biome,lod,nodes
OUT=ROOT/'output/planets/realism'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Open_Planet_Realism_Priorities.blend'))
s=bpy.context.scene;r=next(o for o in s.objects if o.get('op_root'));r['lod_auto']=False
display=[m for o in r.children if o.get('op_role') in {'SURFACE','FAR_SURFACE','CLOUDS','BIOME_INSTANCES'} for m in o.modifiers if m.type=='NODES']
for m in display:m.show_viewport=False
report={}
for name in ('Forest','Grassland','Alpine','Desert','Ocean'):
    cam=bpy.data.objects['Entry Camera · '+name];s.camera=cam;corrected=0;minimum=1e30;poses=[]
    assert cam.parent==r.parent
    # Read original interpolation first; inserting keys while evaluating would
    # otherwise alter the remainder of the authored route.
    for frame in range(1,241):
        s.frame_set(frame);bpy.context.view_layer.update()
        cp,_=lod.logical_camera(r,cam.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        ground=biome.sample(s,r,[tuple(cp.normalized())])[0][0].length;clearance=(cp.length-ground)*6371000.
        if clearance<1.:
            cp=cp.normalized()*(ground+2.5/6371000.);corrected+=1
        poses.append((frame,r.matrix_local@cp));minimum=min(minimum,clearance)
    for frame,location in poses:
        cam.location=location;cam.keyframe_insert('location',frame=frame)
    for fc in biome.curves(cam):
        if fc.data_path=='location':
            for key in fc.keyframe_points:key.interpolation='LINEAR'
    report[name]=dict(corrected_frames=corrected,previous_minimum_clearance_m=minimum)
    print('REVIEW_PATH_REPAIRED',name,report[name],flush=True)
for m in display:m.show_viewport=True
r['lod_auto']=True;s.camera=bpy.data.objects['Entry Camera · Forest'];s.oplab.entry_camera=s.camera;s.frame_set(240);bpy.context.view_layer.update();lod.update(s,r,True)
nodes.refresh_loaded_controls(r);bpy.context.view_layer.update()
# Only unused data in this review copy is purged; the preserved baseline stays intact.
bpy.ops.outliner.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True)
(OUT/'path_repairs.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Open_Planet_Realism_Priorities.blend'),compress=True)
print('REALISM_PATHS_SAVED',flush=True)
