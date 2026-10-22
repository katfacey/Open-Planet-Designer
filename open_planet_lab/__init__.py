# SPDX-License-Identifier: GPL-3.0-or-later
bl_info={'name':'Open Planet Designer','author':'Open Planet Designer contributors','version':(1,4,0),
         'blender':(5,0,0),'location':'View3D > N sidebar > Open Planet',
         'description':'Beta: procedural worlds, real terrain, living surfaces and camera-adaptive detail',
         'doc_url':'https://github.com/katfacey/Open-Planet-Designer',
         'tracker_url':'https://github.com/katfacey/Open-Planet-Designer/issues',
         'category':'Add Mesh'}
import bpy
from bpy.props import EnumProperty,PointerProperty,FloatProperty
# Standard Blender add-on reload support: an update must refresh dependencies,
# rather than leaving the previous generator/shader modules in Python's cache.
if 'generator' in globals():
    import importlib
    from . import presets,nodes,lod_mesh,lod,generator,biome,ecology,terrain_regions,realism,look_math,ground,air,lookdev
    for module in (presets,nodes,lod_mesh,ecology,terrain_regions,lod,generator,biome,realism,look_math,ground,air,lookdev):importlib.reload(module)
from .presets import PRESETS,LABELS,BASE,RANGES
from . import generator,lod

class OP_LODSettings(bpy.types.PropertyGroup):
    camera:PointerProperty(name='LOD camera',type=bpy.types.Object,poll=lambda self,obj:obj.type=='CAMERA')
    biome_mode:EnumProperty(name='Biome',items=[('0','Climate map',''),('1','Grassland',''),('2','Forest',''),
        ('3','Ocean',''),('4','Alpine',''),('5','Desert','')],
        get=lambda self:int(self.id_data.get('biome_mode',0)),set=lambda self,v:self.id_data.__setitem__('biome_mode',v))

# Display lengths in the scene's units; keep normalized controls internally so
# changing planet radius scales the whole ecology consistently.
LIVING_LENGTHS=('biome_relief','biome_mountains','biome_canyons','biome_tree_height','biome_grass_height',
                'biome_rock_size','biome_fern_height','biome_range','biome_tree_distance','biome_wave_height','biome_wave_length','biome_shadow_distance','biome_view_distance')
def living_length(key):
    def get(self):return float(self.id_data.get(key,BASE[key]))*float(self.id_data.get('radius',BASE['radius']))
    def set(self,value):
        root=self.id_data;lo,hi=RANGES[key]
        root[key]=max(lo,min(hi,value/max(.000001,float(root['radius']))));root.update_tag()
    return FloatProperty(name=LABELS[key].replace(' / radius',''),get=get,set=set,min=0.,max=100000000.,
                         subtype='DISTANCE',unit='LENGTH',precision=3)
for _length in LIVING_LENGTHS:OP_LODSettings.__annotations__['size_'+_length]=living_length(_length)

class OP_OT_biome_enable(bpy.types.Operator):
    bl_idname='oplab.biome_enable';bl_label='Build / Upgrade Living Surface';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        from . import biome
        root=generator.active_root(context)
        if not root:return {'CANCELLED'}
        if root['op_kind']!='ROCK':self.report({'ERROR'},'Living biomes require a rocky planet');return {'CANCELLED'}
        biome.enable(context.scene,root);return {'FINISHED'}

class OP_OT_realism_enable(bpy.types.Operator):
    bl_idname='oplab.realism_enable';bl_label='Upgrade Terrain & Forest Structure';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        from . import biome,terrain_regions
        root=generator.active_root(context)
        if not root or root['op_kind']!='ROCK':return {'CANCELLED'}
        biome.ensure(root);root['biome_realism']=True
        generator.upgrade_entry(context.scene,root,refresh=False)
        terrain_regions.configure(context.scene,root)
        biome.enable(context.scene,root)
        self.report({'INFO'},'Coherent habitat and available measured terrain regions enabled')
        return {'FINISHED'}

class OP_OT_lod_enable(bpy.types.Operator):
    bl_idname='oplab.lod_enable';bl_label='Enable / Upgrade Camera LOD';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        r=generator.active_root(context)
        if not r:return {'CANCELLED'}
        r.op_lod.camera=r.op_lod.camera or context.scene.camera
        if not r.op_lod.camera:self.report({'ERROR'},'Add or choose a scene camera first');return {'CANCELLED'}
        generator.upgrade_entry(context.scene,r)
        cam=r.op_lod.camera;cam.data.clip_start=max(.000001,float(r['radius'])*.0000001)
        cam.data.clip_end=max(cam.data.clip_end,float(r['radius'])*12.)
        self.report({'INFO'},r.get('op_lod_status','Camera LOD enabled'));return {'FINISHED'}

class OP_OT_look_enable(bpy.types.Operator):
    bl_idname='oplab.look_enable';bl_label='Upgrade Daylight & Ground';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        from . import lookdev
        root=generator.active_root(context)
        if not root:return {'CANCELLED'}
        try:lookdev.enable(context.scene,root)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self.report({'INFO'},'Development daylight enabled. Bake lighting after locking the shot.')
        return {'FINISHED'}

class OP_OT_look_bake(bpy.types.Operator):
    bl_idname='oplab.look_bake';bl_label='Bake Current Shot Lighting'
    def execute(self,context):
        from . import lookdev
        root=generator.active_root(context)
        if not root:return {'CANCELLED'}
        try:lookdev.bake(context.scene,root)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self.report({'INFO'},'Finite indirect-light capture baked for this static shot')
        return {'FINISHED'}

class OP_OT_look_disable(bpy.types.Operator):
    bl_idname='oplab.look_disable';bl_label='Restore Beta Daylight';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        from . import lookdev
        root=generator.active_root(context)
        if root:lookdev.disable(context.scene,root)
        return {'FINISHED'}

class OP_OT_lod_refresh(bpy.types.Operator):
    bl_idname='oplab.lod_refresh';bl_label='Refresh Camera Detail';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        r=generator.active_root(context)
        if r:lod.update(context.scene,r,True)
        return {'FINISHED'}

class OP_OT_lod_restore(bpy.types.Operator):
    bl_idname='oplab.lod_restore';bl_label='Restore Uniform Meshes';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        r=generator.active_root(context)
        if r:
            if r.get('biome_enabled'):r['lod_enabled']=False;r['op_lod_status']='Living geometry frozen';r.update_tag()
            else:lod.restore_uniform(r)
        return {'FINISHED'}

class OP_OT_entry_demo(bpy.types.Operator):
    bl_idname='oplab.entry_demo';bl_label='New Atmospheric Entry Shot';bl_options={'REGISTER','UNDO'}
    def execute(self,context):generator.create_entry_demo();return {'FINISHED'}

class OP_Settings(bpy.types.PropertyGroup):
    entry_camera:PointerProperty(name='Shot camera',type=bpy.types.Object,poll=lambda self,obj:obj.type=='CAMERA',
        update=lambda self,context:setattr(context.scene,'camera',self.entry_camera) if self.entry_camera else None)
    preset:EnumProperty(name='World',items=[(k,v[0],'Create '+v[0]) for k,v in PRESETS.items()])
    quality:EnumProperty(name='Mesh resolution',items=[('128','Preview Â· 8k','128 Ã— 64'),('256','Standard Â· 33k','256 Ã— 128'),('512','High Â· 131k','512 Ã— 256')],default='256')

class OP_OT_create(bpy.types.Operator):
    bl_idname='oplab.create';bl_label='Create Planet';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        s=context.scene.oplab;generator.create_planet(context.scene,s.preset,int(s.quality),context.scene.cursor.location)
        return {'FINISHED'}

class OP_OT_demo(bpy.types.Operator):
    bl_idname='oplab.demo';bl_label='New Terra Demo Scene';bl_options={'REGISTER','UNDO'}
    def execute(self,context):generator.create_demo();return {'FINISHED'}

class OP_OT_engine(bpy.types.Operator):
    bl_idname='oplab.toggle_engine';bl_label='Switch Eevee / Cycles'
    def execute(self,context):
        s=context.scene;s.render.engine='CYCLES' if s.render.engine=='BLENDER_EEVEE' else 'BLENDER_EEVEE';return {'FINISHED'}

class OP_OT_setup(bpy.types.Operator):
    bl_idname='oplab.setup';bl_label='Set Up Space Render';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        generator.configure(context.scene)
        r=generator.active_root(context)
        if not context.scene.camera:generator.camera(context.scene,target=r.location if r else (0,0,0))
        return {'FINISHED'}

class OP_OT_keyframe(bpy.types.Operator):
    bl_idname='oplab.keyframe';bl_label='Keyframe World Controls';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        r=generator.active_root(context)
        if not r:return {'CANCELLED'}
        from .presets import BASE
        for k in BASE:r.keyframe_insert(data_path='["%s"]'%k)
        self.report({'INFO'},'Planet controls keyframed at frame %d'%context.scene.frame_current);return {'FINISHED'}

class OP_PT_main(bpy.types.Panel):
    bl_label='Open Planet Designer (Beta)';bl_idname='OP_PT_main';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Open Planet'
    def draw(self,context):
        l=self.layout;s=context.scene.oplab;l.prop(s,'preset');l.prop(s,'quality');l.operator('oplab.create',icon='WORLD')
        row=l.row(align=True);row.operator('oplab.demo',text='Demo');row.operator('oplab.setup',text='Space Render')
        l.operator('oplab.entry_demo',icon='CAMERA_DATA')
        l.prop(s,'entry_camera')
        l.separator();l.label(text='Engine: '+context.scene.render.engine.replace('BLENDER_',''));l.operator('oplab.toggle_engine',icon='FILE_REFRESH')
        r=generator.active_root(context)
        if r:l.label(text=r.name,icon='OUTLINER_OB_EMPTY');l.operator('oplab.keyframe',icon='KEY_HLT')
        else:l.label(text='Select a planet layer to edit')

class WorldPanel:
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Open Planet';bl_parent_id='OP_PT_main';bl_options={'DEFAULT_CLOSED'}
    keys=()
    @classmethod
    def poll(cls,context):return generator.active_root(context) is not None
    def draw(self,context):
        r=generator.active_root(context)
        for k in self.keys:self.layout.prop(r,'["%s"]'%k,text=LABELS[k],slider=True)

class OP_PT_terrain(WorldPanel,bpy.types.Panel):
    bl_label='Surface & Terrain';bl_idname='OP_PT_terrain'
    keys=('seed','radius','terrain_scale','detail','sea_level','relief','crater_amount','crater_scale','ice','ocean_glint','city_lights','lava','band_scale','storm','star_strength')
class OP_PT_clouds(WorldPanel,bpy.types.Panel):
    bl_label='Clouds & Atmosphere';bl_idname='OP_PT_clouds'
    keys=('cloud_coverage','cloud_scale','cloud_height','cloud_depth','cloud_rotation','atmosphere','atmosphere_height','haze')
class OP_PT_rings(WorldPanel,bpy.types.Panel):
    bl_label='Planetary Rings';bl_idname='OP_PT_rings'
    keys=('rings','ring_inner','ring_outer','ring_density','ring_tilt','ring_seed')
class OP_PT_lighting(WorldPanel,bpy.types.Panel):
    bl_label='Lighting & Palette';bl_idname='OP_PT_lighting'
    keys=('sun_azimuth','sun_elevation','exposure','night_fill','land_color','high_color','ocean_color','ice_color','cloud_color','atmosphere_color','ring_color','star_color')

class OP_PT_lod(WorldPanel,bpy.types.Panel):
    bl_label='Camera Detail & Entry';bl_idname='OP_PT_lod';bl_options=set()
    def draw(self,context):
        l=self.layout;r=generator.active_root(context)
        l.prop(r.op_lod,'camera')
        if 'lod_enabled' not in r:l.operator('oplab.lod_enable');return
        l.prop(r,'["lod_enabled"]',text='Camera adaptive detail')
        l.prop(r,'["lod_auto"]',text='Live camera updates')
        if 'lod_fit_clip' in r:l.prop(r,'["lod_fit_clip"]',text='Fit camera clipping to planet')
        l.operator('oplab.lod_enable',text='Upgrade / Rebuild Entry Materials')
        for key in ('lod_budget','lod_pixels','lod_near','lod_far','lod_max_depth','lod_micro_height','lod_micro_scale','lod_micro_normal','lod_ao'):
            l.prop(r,'["%s"]'%key,text=LABELS[key])
        l.label(text='Distances are fractions of planet radius')
        l.label(text='Near %.6g / Far %.6g scene units'%(r['radius']*r['lod_near'],r['radius']*r['lod_far']))
        l.label(text=r.get('op_lod_status','Enable to generate adaptive geometry'))
        l.operator('oplab.lod_refresh',icon='FILE_REFRESH')
        l.operator('oplab.lod_restore',text='Freeze Living Geometry' if r.get('biome_enabled') else 'Restore Uniform Meshes')

class OP_PT_biome(WorldPanel,bpy.types.Panel):
    bl_label='Living Surface Â· Real Geometry';bl_idname='OP_PT_biome'
    def draw(self,context):
        l=self.layout;r=generator.active_root(context)
        l.operator('oplab.biome_enable',icon='OUTLINER_OB_POINTCLOUD')
        l.operator('oplab.realism_enable',icon='OUTLINER_OB_GROUP_INSTANCE')
        if 'biome_enabled' not in r:return
        l.prop(r,'["biome_enabled"]',text='Living surface geometry');l.prop(r.op_lod,'biome_mode')
        for key in LIVING_LENGTHS:l.prop(r.op_lod,'size_'+key)
        for key in ('biome_density','biome_budget','biome_instances'):
            l.prop(r,'["%s"]'%key,text=LABELS[key])
        if r.get('biome_realism'):
            l.prop(r,'["biome_region_strength"]',text=LABELS['biome_region_strength'])
            l.label(text='Stable plants Â· source-derived distant crowns')
            import json
            l.label(text='%s measured terrain regions'%len(json.loads(r.get('op_terrain_regions','[]'))))
        l.label(text='Sizes and distances use scene length units')
        l.label(text=r.get('op_biome_status','Build the living surface to scatter models'))
        l.label(text='Terrain + scatter: %s triangles'%format(r.get('op_total_triangles',0),','))
        l.label(text='CC0 assets Â· Poly Haven')

class OP_PT_look(WorldPanel,bpy.types.Panel):
    bl_label='Development · Daylight & Ground';bl_idname='OP_PT_look'
    def draw(self,context):
        l=self.layout;r=generator.active_root(context)
        l.operator('oplab.look_enable',icon='WORLD')
        if not r.get('look_enabled'):
            l.label(text='Optional · Blender 5.2+ · living rocky worlds')
            return
        for key in ('look_texture_scale','look_moisture','look_air_density','look_aerosol','look_sky_strength','look_shadow_texel'):
            l.prop(r,'["%s"]'%key,text=LABELS[key])
        l.operator('oplab.lod_refresh',text='Refresh Ground & Daylight',icon='FILE_REFRESH')
        l.separator()
        for key in ('look_probe_extent','look_probe_capture','look_probe_resolution','look_probe_samples'):
            l.prop(r,'["%s"]'%key,text=LABELS[key])
        l.operator('oplab.look_bake',icon='LIGHTPROBE_VOLUME')
        l.label(text=r.get('op_gi_status','Bake after locking the shot'))
        l.label(text='Static local capture; changing detail needs a new bake')
        l.label(text='Clear-air preview; cloud passage remains in development')
        l.operator('oplab.look_disable')

classes=(OP_LODSettings,OP_Settings,OP_OT_create,OP_OT_demo,OP_OT_engine,OP_OT_setup,OP_OT_keyframe,
    OP_OT_lod_enable,OP_OT_lod_refresh,OP_OT_lod_restore,OP_OT_entry_demo,OP_OT_biome_enable,OP_OT_realism_enable,
    OP_OT_look_enable,OP_OT_look_bake,OP_OT_look_disable,
    OP_PT_main,OP_PT_terrain,OP_PT_clouds,OP_PT_rings,OP_PT_lighting,OP_PT_lod,OP_PT_biome,OP_PT_look)
def register():
    for c in classes:bpy.utils.register_class(c)
    bpy.types.Scene.oplab=bpy.props.PointerProperty(type=OP_Settings)
    bpy.types.Object.op_lod=PointerProperty(type=OP_LODSettings)
    lod.register()
def unregister():
    lod.unregister();del bpy.types.Object.op_lod;del bpy.types.Scene.oplab
    for c in reversed(classes):bpy.utils.unregister_class(c)
