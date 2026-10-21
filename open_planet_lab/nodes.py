# SPDX-License-Identifier: GPL-3.0-or-later
"""Small node graph builder for shared, inspectable engine-independent graphs."""
import math
from pathlib import Path
import bpy
from .presets import BASE, LABELS
WAVES=(((1.,.23,.31),1.,1.),((.81,.37,-.42),1.73,.42),((.47,-.29,.83),2.61,.23),
       ((-.32,.91,.24),4.17,.12),((.2,.5,-.84),7.2,.055),((.68,.21,.37),13.3,.026),
       ((.4,-.63,.18),23.5,.012),((-.2,.7,.61),37.7,.006))

class Graph:
    def __init__(self, tree):
        self.tree=tree; self.nodes=tree.nodes; self.links=tree.links; self.count=0
    def node(self, kind, label='', **kw):
        n=self.nodes.new(kind); n.label=label; n.name=label or n.name
        n.location=((self.count%7)*210, -(self.count//7)*220); self.count+=1
        for k,v in kw.items(): setattr(n,k,v)
        return n
    def put(self, val, socket):
        if hasattr(val,'is_output'): self.links.new(val,socket)
        else:
            if socket.type=='VECTOR' and isinstance(val,(tuple,list)) and len(val)==4:val=val[:3]
            socket.default_value=val
    def math(self, op, a, b=None, c=None, label=''):
        n=self.node('ShaderNodeMath',label or op,operation=op)
        for i,v in enumerate((a,b,c)):
            if v is not None:self.put(v,n.inputs[i])
        return n.outputs[0]
    def vec(self, op, a, b=None, scale=None):
        n=self.node('ShaderNodeVectorMath',op,operation=op); self.put(a,n.inputs[0])
        if b is not None:self.put(b,n.inputs[1])
        if scale is not None:self.put(scale,n.inputs['Scale'])
        return n.outputs['Value'] if op in {'DOT_PRODUCT','DISTANCE','LENGTH'} else n.outputs['Vector']
    def xyz(self, v):
        n=self.node('ShaderNodeSeparateXYZ'); self.put(v,n.inputs[0]); return tuple(n.outputs)
    def combine(self, x,y,z):
        n=self.node('ShaderNodeCombineXYZ')
        for v,s in zip((x,y,z),n.inputs):self.put(v,s)
        return n.outputs[0]
    def noise(self, v,scale=1.,detail=4.,rough=.65, distortion=0.,seed=0.):
        n=self.node('ShaderNodeTexNoise','Fractal field',noise_dimensions='4D')
        for k,x in [('Vector',v),('Scale',scale),('Detail',detail),('Roughness',rough),('Distortion',distortion),('W',seed)]:self.put(x,n.inputs[k])
        return n.outputs['Fac']
    def ramp(self, val, stops, interpolation='LINEAR', label='Palette'):
        n=self.node('ShaderNodeValToRGB',label); n.color_ramp.interpolation=interpolation
        for p,c in stops[2:]:n.color_ramp.elements.new(p)
        for e,(p,c) in zip(n.color_ramp.elements,stops):e.position=p; e.color=c
        self.put(val,n.inputs[0]); return n.outputs['Color']
    def mix(self,fac,a,b):
        n=self.node('ShaderNodeMixRGB','Blend',blend_type='MIX');self.put(fac,n.inputs[0]);self.put(a,n.inputs[1]);self.put(b,n.inputs[2]);return n.outputs[0]
    def rgbscale(self,color,fac):return self.vec('SCALE',color,scale=fac)
    def smooth(self,val,a,b):
        n=self.node('ShaderNodeMapRange','Soft threshold',interpolation_type='SMOOTHSTEP');n.clamp=True
        for k,x in [('Value',val),('From Min',a),('From Max',b),('To Min',0.),('To Max',1.)]:self.put(x,n.inputs[k])
        return n.outputs[0]

def drive(socket,root,key,expr='v'):
    d=socket.driver_add('default_value').driver; d.type='SCRIPTED';d.expression=expr
    v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=root;v.targets[0].data_path='["%s"]'%key

def controls(root):
    t=bpy.data.node_groups.new(root.name+' Â· Parameters','ShaderNodeTree');g=Graph(t)
    out=g.node('NodeGroupOutput','ANIMATABLE WORLD CONTROLS');out.location=(400,0)
    for i,(k,v) in enumerate(BASE.items()):
        iscolor=k.endswith('_color'); typ='NodeSocketColor' if iscolor else 'NodeSocketFloat'
        s=t.interface.new_socket(name=LABELS[k],in_out='OUTPUT',socket_type=typ)
        s.description='Driven by '+root.name+' custom property '+k
        n=g.node('ShaderNodeRGB' if iscolor else 'ShaderNodeValue',LABELS[k]);n.location=(-500+(i//16)*220,-(i%16)*85)
        n.outputs[0].default_value=root[k]
        if iscolor:
            for j in range(4):
                d=n.outputs[0].driver_add('default_value',j).driver;d.expression='v'
                v=d.variables.new();v.name='v';v.type='SINGLE_PROP';v.targets[0].id=root;v.targets[0].data_path='["%s"][%d]'%(k,j)
        else:
            # Blender's animation value-change tolerance can discard tiny
            # radius-normalized values. Drive a well-scaled value, then convert
            # in the graph, where small geometry/shader fields remain intact.
            factor=1000000. if isinstance(BASE[k],float) and abs(BASE[k])<.01 else 1.
            n.outputs[0].default_value=root[k]*factor
            drive(n.outputs[0],root,k,'v*1000000' if factor>1 else 'v')
        value=n.outputs[0]
        if not iscolor and factor>1:value=g.math('MULTIPLY',value,.000001,label='Radius-unit '+LABELS[k])
        g.links.new(value,out.inputs[LABELS[k]])
    return t

def params(g,t,root=None):
    if root is not None:g.root=root
    if g.tree.bl_idname=='GeometryNodeTree':
        result={}
        for k,v in BASE.items():
            if k.endswith('_color'):continue
            factor=1000000. if isinstance(BASE[k],float) and abs(BASE[k])<.01 else 1.
            n=g.node('ShaderNodeValue',LABELS[k]);n.outputs[0].default_value=root[k]*factor
            drive(n.outputs[0],root,k,'v*1000000' if factor>1 else 'v')
            result[k]=g.math('MULTIPLY',n.outputs[0],.000001,label='Radius-unit '+LABELS[k]) if factor>1 else n.outputs[0]
        return result
    n=g.node('ShaderNodeGroup','WORLD CONTROLS Â· select planet â†’ N â†’ Open Planet');n.node_tree=t;n.width=290
    return {k:n.outputs[LABELS[k]] for k in BASE}

def refresh_loaded_controls(root):
    """Invalidate loaded shader parameter caches without changing the frame.

    The live viewport can retain unevaluated driven group values after loading
    with script execution disabled. Reassert their saved property values and
    tag the trees; the simple-expression drivers remain attached and editable.
    """
    tree=bpy.data.node_groups.get(root.get('op_controls',''))
    if not tree:return
    for key,default in BASE.items():
        node=tree.nodes.get(LABELS[key])
        if not node:continue
        value=root.get(key,default)
        if key.endswith('_color'):node.outputs[0].default_value=tuple(value)
        else:
            factor=1000000. if isinstance(default,float) and abs(default)<.01 else 1.
            node.outputs[0].default_value=float(value)*factor
    tree.update_tag()
    root.update_tag(refresh={'OBJECT','DATA','TIME'})
    for ob in root.children:
        if ob.type!='MESH':continue
        for material in ob.data.materials:
            if material and material.node_tree:material.node_tree.update_tag()

def terrain_field(g,v,p):
    # The same field drives the mesh and the surface palette.
    return g.noise(v,p['terrain_scale'],p['detail'],.57,0.,p['seed'])

def anchor(g,root):
    values=[]
    for axis in 'xyz':
        key='op_anchor_'+axis
        if key not in root:root[key]=0.
        node=g.node('ShaderNodeValue','Local origin '+axis);drive(node.outputs[0],root,key);values.append(node.outputs[0])
    return g.combine(*values)

def ground_texture(g,coords,name,channel='color',frequency=3000000.):
    path=Path(__file__).parent/'assets/ground'/(name+'_'+channel+('.jpg' if channel=='color' else '.png'))
    if not path.exists():return None
    im=bpy.data.images.load(str(path),check_existing=True)
    if channel!='color':im.colorspace_settings.name='Non-Color'
    if not im.packed_file:im.pack()
    node=g.node('ShaderNodeTexImage','CC0 '+name+' '+channel);node.image=im
    node.projection='BOX';node.projection_blend=.25
    g.put(g.vec('SCALE',coords,scale=g.math('MULTIPLY',frequency/1000.,1000.)),node.inputs['Vector'])
    return node.outputs['Color']

def elevation_tile(g,v,name):
    """Geographic height, sampled identically by shader and Geometry Nodes."""
    path=Path(__file__).parent/'assets/terrain'/(name+'.png')
    if not path.exists():return None
    image=bpy.data.images.load(str(path),check_existing=True);image.colorspace_settings.name='Non-Color'
    if not image.packed_file:image.pack()
    x,y,z=g.xyz(v)
    u=g.math('FRACT',g.math('MULTIPLY',g.math('MULTIPLY_ADD',g.math('ARCTAN2',y,x),1/math.tau,.5),384.))
    w=g.math('FRACT',g.math('MULTIPLY',g.math('DIVIDE',g.math('ARCCOSINE',g.math('MINIMUM',g.math('MAXIMUM',z,-1.),1.)),math.pi),192.))
    coords=g.combine(u,w,0.)
    if g.tree.bl_idname=='GeometryNodeTree':
        node=g.node('GeometryNodeImageTexture','USGS '+name,interpolation='Linear',extension='REPEAT')
        node.inputs['Image'].default_value=image
    else:
        node=g.node('ShaderNodeTexImage','USGS '+name);node.image=image;node.interpolation='Linear'
    g.put(coords,node.inputs['Vector'])
    edge=g.math('MINIMUM',g.math('MINIMUM',u,w),g.math('MINIMUM',g.math('SUBTRACT',1.,u),g.math('SUBTRACT',1.,w)))
    mask=g.smooth(edge,.01,.10)
    # Blend tile edges into procedural terrain, avoiding elevation discontinuities.
    return g.math('ADD',g.math('MULTIPLY',node.outputs['Color'],mask),g.math('MULTIPLY',g.math('SUBTRACT',1.,mask),.30))

def biome_fields(g,v,p):
    """World-anchored climate and elevation; identical in geometry and materials.

    Mode 0 is climate-driven; 1..5 are grass, forest, ocean, alpine and desert.
    Overrides affect the world, never the camera or the current altitude.
    """
    cont=terrain_field(g,v,p);mode=p['biome_mode']
    forced=[g.math('COMPARE',mode,float(i),.1) for i in range(6)]
    land=g.smooth(cont,p['sea_level'],g.math('ADD',p['sea_level'],.018))
    land=g.math('MULTIPLY',land,g.math('SUBTRACT',1.,forced[3]))
    moisture=g.noise(v,7.8,3.,.62,0.,g.math('ADD',p['seed'],13.))
    mountain=g.smooth(g.noise(v,11.,3.,.64,0.,g.math('ADD',p['seed'],57.)),.44,.66)
    desert=g.math('SUBTRACT',1.,g.smooth(moisture,.40,.53))
    forest=g.smooth(moisture,.49,.61)
    mountain=g.math('ADD',g.math('MULTIPLY',forced[0],mountain),forced[4])
    desert=g.math('ADD',g.math('MULTIPLY',forced[0],desert),forced[5])
    forest=g.math('ADD',g.math('MULTIPLY',forced[0],forest),forced[2])
    forest=g.math('MULTIPLY',forest,g.math('SUBTRACT',1.,mountain))
    grass=g.math('SUBTRACT',1.,g.math('MAXIMUM',desert,g.math('MAXIMUM',forest,mountain)))
    forest=g.math('MULTIPLY',forest,land);desert=g.math('MULTIPLY',desert,land)
    grass=g.math('MULTIPLY',grass,land);mountain=g.math('MULTIPLY',mountain,land)
    warp=g.vec('ADD',v,g.vec('SCALE',(1.,.42,-.58),scale=g.math('MULTIPLY',g.noise(v,23.,3.),.007)))
    ridge=0.
    for frequency,amplitude in ((130.,.42),(270.,.24),(570.,.15),(1200.,.09),(2500.,.06),(5300.,.04)):
        r=g.math('SUBTRACT',1.,g.math('ABSOLUTE',g.math('MULTIPLY_ADD',g.noise(warp,frequency,0.,.5,0.,p['seed']),2.,-1.)))
        ridge=g.math('ADD',ridge,g.math('MULTIPLY',g.math('POWER',r,5.),amplitude))
    drainage=g.node('ShaderNodeTexVoronoi','Eroded canyon network',feature='DISTANCE_TO_EDGE')
    g.put(warp,drainage.inputs['Vector']);drainage.inputs['Scale'].default_value=350.
    channel=g.math('SUBTRACT',1.,g.smooth(drainage.outputs['Distance'],.048,.073))
    canyon_height=g.math('SUBTRACT',1.,channel)
    realism=bool(getattr(g,'root',None) is not None and g.root.get('biome_realism'))
    measured_peak=None if realism else elevation_tile(g,v,'rainier');measured_canyon=None if realism else elevation_tile(g,v,'grand_canyon')
    if measured_peak is not None:ridge=g.math('ADD',g.math('MULTIPLY',ridge,.15),g.math('MULTIPLY',measured_peak,.85))
    if measured_canyon is not None:
        canyon_height=g.math('ADD',g.math('MULTIPLY',canyon_height,.10),g.math('MULTIPLY',measured_canyon,.90))
        channel=g.math('SUBTRACT',1.,g.smooth(measured_canyon,.20,.55))
    plateau=g.math('MULTIPLY',canyon_height,g.math('MULTIPLY',desert,p['biome_canyons']))
    elevation=g.math('MULTIPLY',g.math('MAXIMUM',g.math('SUBTRACT',cont,p['sea_level']),0.),p['biome_relief'])
    hills=g.math('MULTIPLY',g.math('SUBTRACT',g.noise(v,1800.,4.,.55,0.,p['seed']),.35),.000018)
    # A continuous middle scale avoids a smooth plain between continental
    # relief and centimetre grain. These are genuine ground shapes.
    for frequency,amplitude in ((18000.,.0000028),(95000.,.00000042),(480000.,.000000045)):
        hills=g.math('ADD',hills,g.math('MULTIPLY',g.math('SUBTRACT',g.noise(v,frequency,2.,.58,0.,p['seed']),.5),amplitude))
    peaks=g.math('MULTIPLY',g.math('MULTIPLY',mountain,ridge),p['biome_mountains'])
    height=g.math('MULTIPLY',land,g.math('ADD',elevation,g.math('ADD',hills,g.math('ADD',peaks,plateau))))
    if realism:
        from . import terrain_regions
        height,ridge=terrain_regions.apply_field(g,v,p,height,ridge)
    cover=g.noise(v,140000.,2.,.65,0.,g.math('ADD',p['seed'],73.))
    return dict(land=land,forest=forest,grass=grass,desert=desert,mountain=mountain,cover=cover,
                canyon=channel,height=height,continent=cont,mountain_relief=ridge)

def wave_offset(g,v,p,b,localpos=None,root=None):
    """Five animated geometric swells with bounded, tangent crest compression."""
    radial=0.;horizontal=(0.,0.,0.)
    for i,(direction,mul,amp) in enumerate(WAVES):
        direction=tuple(VectorUnit(direction))
        frequency=g.math('DIVIDE',math.tau*mul,p['biome_wave_length'])
        projection=g.math('MULTIPLY',g.vec('DOT_PRODUCT',localpos if localpos is not None else v,direction),frequency)
        if root is not None:
            key='op_wave_phase'+str(i)
            if key not in root:root[key]=0.
            n=g.node('ShaderNodeValue','Stable wave phase '+str(i));drive(n.outputs[0],root,key)
            projection=g.math('ADD',projection,n.outputs[0])
        phase=g.math('ADD',projection,
                     g.math('MULTIPLY',p['biome_time'],1.2*math.sqrt(mul)))
        a=g.math('MULTIPLY',p['biome_wave_height'],amp)
        radial=g.math('ADD',radial,g.math('MULTIPLY',g.math('SINE',phase),a))
        tangent=g.vec('SUBTRACT',direction,g.vec('SCALE',v,scale=g.vec('DOT_PRODUCT',v,direction)))
        horizontal=g.vec('ADD',horizontal,g.vec('SCALE',tangent,scale=g.math('MULTIPLY',g.math('COSINE',phase),g.math('MULTIPLY',a,.32))))
    wet=g.math('SUBTRACT',1.,b['land'])
    return g.vec('SCALE',g.vec('ADD',g.vec('SCALE',v,scale=radial),horizontal),scale=wet)

def VectorUnit(v):
    length=math.sqrt(sum(x*x for x in v));return (x/length for x in v)

def sun_vector(g,p):
    a=g.math('MULTIPLY',p['sun_azimuth'],math.pi/180);e=g.math('MULTIPLY',p['sun_elevation'],math.pi/180)
    ce=g.math('COSINE',e)
    return g.combine(g.math('MULTIPLY',g.math('SINE',a),ce),g.math('MULTIPLY',g.math('COSINE',a),g.math('MULTIPLY',ce,-1)),g.math('SINE',e))

def local_sun(g,p):
    n=g.node('ShaderNodeVectorTransform',vector_type='VECTOR',convert_from='WORLD',convert_to='OBJECT');g.put(sun_vector(g,p),n.inputs[0])
    return g.vec('NORMALIZE',n.outputs[0])

def cloud_field(g,v,p):
    n=g.node('ShaderNodeVectorRotate','Cloud drift',rotation_type='AXIS_ANGLE');g.put(v,n.inputs['Vector'])
    n.inputs['Axis'].default_value=(0.,0.,1.);g.put(g.math('MULTIPLY',p['cloud_rotation'],-math.pi/180),n.inputs['Angle'])
    f=g.noise(n.outputs[0],p['cloud_scale'],7.,.72,1.7,p['seed'])
    w=g.noise(n.outputs[0],58.,3.,.7,1.1,p['seed'])
    f=g.math('ADD',f,g.math('MULTIPLY',w,.12))
    threshold=g.math('SUBTRACT',.82,g.math('MULTIPLY',p['cloud_coverage'],.49))
    alpha=g.math('MULTIPLY',g.smooth(f,threshold,g.math('ADD',threshold,.075)),g.smooth(p['cloud_coverage'],0.,.03))
    return alpha,w

def ring_shadow(g,v,p):
    tilt=g.math('MULTIPLY',p['ring_tilt'],math.pi/180)
    plane=g.combine(0.,g.math('MULTIPLY',g.math('SINE',tilt),-1.),g.math('COSINE',tilt))
    sd=local_sun(g,p);denom=g.vec('DOT_PRODUCT',sd,plane)
    travel=g.math('DIVIDE',g.math('MULTIPLY',g.vec('DOT_PRODUCT',v,plane),-1.),denom)
    hit=g.vec('ADD',v,g.vec('SCALE',sd,scale=travel));rad=g.vec('LENGTH',hit)
    inner=g.smooth(rad,p['ring_inner'],g.math('ADD',p['ring_inner'],.03))
    outer=g.math('SUBTRACT',1.,g.smooth(rad,g.math('SUBTRACT',p['ring_outer'],.03),p['ring_outer']))
    gap=g.math('SUBTRACT',1.,g.math('MULTIPLY',g.smooth(rad,1.94,1.96),g.math('SUBTRACT',1.,g.smooth(rad,2.03,2.05))))
    # Broad optical depth is stable for subpixel ring shadows on the surface.
    bands=g.noise(g.combine(rad,0.,0.),15.,2.,.65,0.,p['ring_seed'])
    mask=g.math('MULTIPLY',g.math('MULTIPLY',inner,outer),g.math('MULTIPLY',gap,g.math('GREATER_THAN',travel,0.)))
    return g.math('MULTIPLY',mask,g.math('MULTIPLY',p['rings'],g.math('MULTIPLY',p['ring_density'],g.math('MULTIPLY_ADD',bands,.6,.4))))

def lighting(g,n,p,soft=.1):
    dot=g.vec('DOT_PRODUCT',n,sun_vector(g,p))
    day=g.smooth(dot,-soft,.65)
    diffuse=g.math('MULTIPLY',g.math('MAXIMUM',dot,0.),.82)
    diffuse=g.math('ADD',diffuse,g.math('MULTIPLY',day,.18))
    diffuse=g.math('ADD',diffuse,p['night_fill'])
    return g.math('MULTIPLY',diffuse,p['exposure']),dot,day

def mineral_normal(g,v,world_normal,p):
    """Finite differences of one continuous 3D field, shared by both engines."""
    center=g.noise(v,72.,3.,.64,0.,p['seed']);step=.001
    grads=[]
    for off in ((step,0,0),(0,step,0),(0,0,step)):
        sample=g.noise(g.vec('ADD',v,off),72.,3.,.64,0.,p['seed'])
        grads.append(g.math('DIVIDE',g.math('SUBTRACT',sample,center),step))
    grad=g.combine(*grads);grad=g.vec('SUBTRACT',grad,g.vec('SCALE',v,scale=g.vec('DOT_PRODUCT',v,grad)))
    n=g.node('ShaderNodeVectorTransform',vector_type='NORMAL',convert_from='OBJECT',convert_to='WORLD');g.put(grad,n.inputs[0])
    land=g.smooth(terrain_field(g,v,p),p['sea_level'],g.math('ADD',p['sea_level'],.015))
    strength=g.math('MULTIPLY',land,.003)
    return g.vec('NORMALIZE',g.vec('SUBTRACT',world_normal,g.vec('SCALE',n.outputs[0],scale=strength)))

def material(name):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.node_tree.nodes.clear()
    return m,Graph(m.node_tree)

def emission(g,color):
    e=g.node('ShaderNodeEmission','Deterministic radiance');g.put(color,e.inputs['Color']);e.inputs['Strength'].default_value=1.;return e.outputs[0]

def output(g,shader):
    o=g.node('ShaderNodeOutputMaterial','Material output');g.put(shader,o.inputs['Surface']);return o

def add_transparency(g,m,color,alpha,additive=False,facing=None):
    # Front hemisphere only. BLENDED avoids stochastic alpha differences in Eevee.
    try:m.surface_render_method='BLENDED'
    except (AttributeError,TypeError):pass
    if hasattr(m,'use_transparency_overlap'):m.use_transparency_overlap=facing is not None
    geo=g.node('ShaderNodeNewGeometry');front=g.math('SUBTRACT',1.,geo.outputs['Backfacing'])
    alpha=g.math('MULTIPLY',alpha,front if facing is None else facing)
    tr=g.node('ShaderNodeBsdfTransparent');e=emission(g,color)
    if additive:
        # Transparent transmission plus additive camera radiance, with no light transport.
        e_node=e.node;g.put(g.rgbscale(color,alpha),e_node.inputs['Color'])
        mix=g.node('ShaderNodeAddShader');g.links.new(tr.outputs[0],mix.inputs[0]);g.links.new(e,mix.inputs[1])
    else:
        mix=g.node('ShaderNodeMixShader');g.put(alpha,mix.inputs[0]);g.links.new(tr.outputs[0],mix.inputs[1]);g.links.new(e,mix.inputs[2])
    output(g,mix.outputs[0])
    return m

def distance_fade(g,p,distance=None):
    if distance is None:
        cam=g.node('ShaderNodeCameraData');distance=g.math('DIVIDE',cam.outputs['View Distance'],p['radius'])
    far=g.math('MAXIMUM',p['lod_far'],g.math('ADD',p['lod_near'],.000001))
    return g.math('MULTIPLY',p['lod_enabled'],g.math('SUBTRACT',1.,g.smooth(distance,p['lod_near'],far)))

def micro_height(g,v,p,fade):
    octaves=g.math('MULTIPLY',fade,4.)
    f=g.noise(v,p['lod_micro_scale'],octaves,.55,0.,p['seed'])
    f=g.math('SUBTRACT',f,.5)
    fine=g.noise(v,g.math('MULTIPLY',p['lod_micro_scale'],4.),octaves,.55,0.,p['seed'])
    f=g.math('ADD',f,g.math('MULTIPLY',g.math('SUBTRACT',fine,.5),.22))
    grit=g.noise(v,g.math('MULTIPLY',p['lod_micro_scale'],64.),g.math('MULTIPLY',fade,2.),.55,0.,p['seed'])
    f=g.math('ADD',f,g.math('MULTIPLY',g.math('SUBTRACT',grit,.5),.012))
    land=g.smooth(terrain_field(g,v,p),p['sea_level'],g.math('ADD',p['sea_level'],.02))
    return g.math('MULTIPLY',f,g.math('MULTIPLY',g.math('MULTIPLY',land,fade),p['lod_micro_height']))

def atmosphere_path(g,p,ground=False,anchor=None):
    """Camera-to-boundary optical depth, valid on either side of the atmosphere.

    Eight midpoint samples integrate exponential density. Shadow/daylight and
    phase are analytic approximations shared by Eevee and Cycles.
    """
    geo=g.node('ShaderNodeNewGeometry');info=g.node('ShaderNodeObjectInfo');cam=g.node('ShaderNodeCameraData')
    center=info.outputs['Location']
    if anchor is not None:
        transform=g.node('ShaderNodeVectorTransform',vector_type='VECTOR',convert_from='OBJECT',convert_to='WORLD');g.put(anchor,transform.inputs[0])
        center=g.vec('SUBTRACT',center,transform.outputs[0])
    pos=g.vec('SCALE',g.vec('SUBTRACT',geo.outputs['Position'],center),scale=g.math('DIVIDE',1.,p['radius']))
    distance=g.math('DIVIDE',cam.outputs['View Distance'],p['radius'])
    incoming=geo.outputs['Incoming'];origin=g.vec('ADD',pos,g.vec('SCALE',incoming,scale=distance));direction=g.vec('SCALE',incoming,scale=-1.)
    b=g.vec('DOT_PRODUCT',origin,direction);o2=g.vec('DOT_PRODUCT',origin,origin)
    outer=g.math('ADD',1.,p['atmosphere_height']);r2=g.math('MULTIPLY',outer,outer)
    disc=g.math('ADD',g.math('MULTIPLY',b,b),g.math('SUBTRACT',r2,o2))
    sq=g.math('SQRT',g.math('MAXIMUM',disc,0.));minus_b=g.math('MULTIPLY',b,-1.)
    start=g.math('MAXIMUM',g.math('SUBTRACT',minus_b,sq),0.);end=g.math('ADD',minus_b,sq)
    if ground:end=g.math('MINIMUM',end,distance)
    else:
        gd=g.math('ADD',g.math('MULTIPLY',b,b),g.math('SUBTRACT',1.,o2))
        hit=g.math('SUBTRACT',minus_b,g.math('SQRT',g.math('MAXIMUM',gd,0.)))
        valid=g.math('MULTIPLY',g.math('GREATER_THAN',gd,0.),g.math('GREATER_THAN',hit,start))
        end=g.math('ADD',g.math('MULTIPLY',valid,g.math('MINIMUM',end,hit)),g.math('MULTIPLY',g.math('SUBTRACT',1.,valid),end))
    length=g.math('MAXIMUM',g.math('SUBTRACT',end,start),0.)
    scaleheight=g.math('MULTIPLY',p['atmosphere_height'],.24);density=0.
    for i in range(8):
        t=g.math('ADD',start,g.math('MULTIPLY',length,(i+.5)/8.))
        point=g.vec('ADD',origin,g.vec('SCALE',direction,scale=t))
        altitude=g.math('MAXIMUM',g.math('SUBTRACT',g.vec('LENGTH',point),1.),0.)
        rho=g.math('EXPONENT',g.math('MULTIPLY',g.math('DIVIDE',altitude,scaleheight),-1.))
        density=g.math('ADD',density,rho)
    tau=g.math('MULTIPLY',g.math('MULTIPLY',density,g.math('DIVIDE',length,8.)),g.math('DIVIDE',g.math('MULTIPLY',p['atmosphere'],.65),scaleheight))
    alpha=g.math('SUBTRACT',1.,g.math('EXPONENT',g.math('MULTIPLY',tau,-1.)))
    midpoint=g.vec('NORMALIZE',g.vec('ADD',origin,g.vec('SCALE',direction,scale=g.math('ADD',start,g.math('MULTIPLY',length,.5)))))
    sun=sun_vector(g,p);day=g.smooth(g.vec('DOT_PRODUCT',midpoint,sun),-.08,.18)
    forward=g.math('POWER',g.math('MAXIMUM',g.vec('DOT_PRODUCT',direction,sun),0.),24.)
    color=g.mix(g.math('MULTIPLY',forward,.55),p['atmosphere_color'],(1.,.65,.30,1))
    color=g.rgbscale(color,g.math('ADD',.008,g.math('MULTIPLY',day,p['exposure'])))
    inside=g.math('LESS_THAN',o2,r2)
    return color,alpha,inside

def aerial_perspective(g,col,p,anchor=None):
    fog,alpha,inside=atmosphere_path(g,p,True,anchor)
    weight=g.math('MULTIPLY',p['lod_enabled'],g.math('MULTIPLY',inside,alpha))
    return g.mix(weight,col,fog)

def entry_normal(g,v,normal,p,fade):
    camera=g.node('ShaderNodeCameraData');distance=g.math('DIVIDE',camera.outputs['View Distance'],p['radius'])
    # Math socket constants clamp at 10,000; form the high-frequency cap in the
    # graph so the close-up field really can reach 300,000 cycles per radius.
    cap=g.math('MULTIPLY',3000.,100.)
    frequency=g.math('MINIMUM',cap,g.math('MAXIMUM',g.math('MULTIPLY',p['lod_micro_scale'],8.),g.math('DIVIDE',4.,g.math('MAXIMUM',distance,.00001))))
    step=g.math('DIVIDE',.04,frequency);center=g.noise(v,frequency,g.math('MULTIPLY',fade,2.),.58,0.,p['seed'])
    center.node.name='Entry mineral field'
    grad=[]
    for axis in range(3):
        xyz=[0.,0.,0.];xyz[axis]=step
        sample=g.noise(g.vec('ADD',v,g.combine(*xyz)),frequency,g.math('MULTIPLY',fade,2.),.58,0.,p['seed'])
        grad.append(g.math('DIVIDE',g.math('SUBTRACT',sample,center),.04))
    perturb=g.combine(*grad);perturb=g.vec('SUBTRACT',perturb,g.vec('SCALE',v,scale=g.vec('DOT_PRODUCT',v,perturb)))
    tr=g.node('ShaderNodeVectorTransform',vector_type='VECTOR',convert_from='OBJECT',convert_to='WORLD');g.put(perturb,tr.inputs[0])
    land=g.smooth(terrain_field(g,v,p),p['sea_level'],g.math('ADD',p['sea_level'],.02))
    strength=g.math('DIVIDE',g.math('MULTIPLY',g.math('MULTIPLY',fade,land),p['lod_micro_normal']),p['radius'])
    return g.vec('NORMALIZE',g.vec('SUBTRACT',normal,g.vec('SCALE',tr.outputs[0],scale=strength))),center

def surface(root,t,kind):
    m,g=material(root.name+' Â· Surface');g.root=root;p=params(g,t)
    tc=g.node('ShaderNodeTexCoord');origin=anchor(g,root) if kind=='ROCK' else None
    v=g.vec('NORMALIZE',g.vec('ADD',tc.outputs['Object'],origin) if origin is not None else tc.outputs['Object']);z=g.xyz(v)[2]
    geo=g.node('ShaderNodeNewGeometry');normal=geo.outputs['Normal']
    field=terrain_field(g,v,p)
    fine=g.noise(v,145.,3.,.7,0.,p['seed'])
    fade=distance_fade(g,p)
    if kind in {'ROCK','BROKEN'}:
        normal=mineral_normal(g,v,normal,p)
        normal,fine_detail=entry_normal(g,tc.outputs['Object'],normal,p,fade)
        # Local strata/crevice contrast fades continuously before the far limit.
        fine=g.math('ADD',fine,g.math('MULTIPLY',g.math('SUBTRACT',fine_detail,.5),g.math('MULTIPLY',fade,p['lod_micro_normal'])))
        if kind=='ROCK':
            # Living surfaces take their large-scale shape from actual mesh normals.
            normal=g.vec('NORMALIZE',g.vec('ADD',g.vec('SCALE',normal,scale=g.math('SUBTRACT',1.,p['biome_enabled'])),
                       g.vec('SCALE',geo.outputs['Normal'],scale=p['biome_enabled'])))
    light,dot,day=lighting(g,normal,p)
    light=g.math('MULTIPLY',light,g.math('SUBTRACT',1.,g.math('MULTIPLY',ring_shadow(g,v,p),.9)))
    if kind=='STAR':
        cells=g.node('ShaderNodeTexVoronoi','Convection granules',feature='DISTANCE_TO_EDGE');g.put(v,cells.inputs['Vector']);cells.inputs['Scale'].default_value=95.
        gran=g.smooth(cells.outputs['Distance'],0.,.1)
        turbulent=g.noise(v,7.,5.,.72,2.,p['seed'])
        spots=g.smooth(turbulent,.28,.42)
        col=g.mix(gran,g.rgbscale(p['star_color'],.24),g.mix(.35,p['star_color'],(1.,.78,.43,1)));col=g.rgbscale(col,g.math('ADD',.2,g.math('MULTIPLY',spots,.8)))
        lw=g.node('ShaderNodeLayerWeight');limb=g.math('ADD',.4,g.math('MULTIPLY',g.math('SUBTRACT',1.,lw.outputs['Facing']),.6))
        col=g.rgbscale(col,g.math('MULTIPLY',p['star_strength'],limb));output(g,emission(g,col));return m
    if kind=='GAS':
        warp=g.noise(v,3.2,5.,.7,2.,p['seed'])
        band=g.math('ADD',g.math('MULTIPLY',z,p['band_scale']),g.math('MULTIPLY',warp,g.math('MULTIPLY',p['storm'],7.)))
        band=g.math('SINE',g.math('MULTIPLY',band,math.tau))
        band=g.math('MULTIPLY_ADD',band,.5,.5)
        band=g.math('ADD',g.math('MULTIPLY',band,.7),g.math('MULTIPLY',g.noise(v,32.,4.,.7,4.,p['seed']),.3))
        col=g.mix(band,p['land_color'],p['high_color'])
        col=g.mix(g.smooth(band,.1,.3),p['ocean_color'],col)
        # A localized, sheared oval vortex on the camera-facing hemisphere.
        x,y,z2=g.xyz(v)
        stormdist=g.vec('LENGTH',g.combine(g.math('MULTIPLY',g.math('ADD',x,.28),2.1),g.math('MULTIPLY',g.math('ADD',y,.90),2.),g.math('MULTIPLY',g.math('ADD',z2,.19),7.)))
        swirl=g.math('SINE',g.math('ADD',g.math('MULTIPLY',stormdist,35.),g.math('MULTIPLY',warp,4.)))
        stormmask=g.math('MULTIPLY',g.math('SUBTRACT',1.,g.smooth(stormdist,.35,1.)),p['storm'])
        col=g.mix(stormmask,col,g.mix(g.math('MULTIPLY_ADD',swirl,.5,.5),p['land_color'],p['high_color']))
    else:
        dry=g.smooth(field,p['sea_level'],g.math('ADD',p['sea_level'],.014))
        altitude=g.smooth(field,.47,.75)
        col=g.mix(altitude,p['land_color'],p['high_color'])
        coast=g.math('MULTIPLY',dry,g.math('SUBTRACT',1.,g.smooth(field,p['sea_level'],g.math('ADD',p['sea_level'],.035))))
        col=g.mix(g.math('MULTIPLY',coast,.45),col,(.33,.24,.11,1))
        # Broad organic erosion plus fine mineral grain.
        grain=g.math('MULTIPLY_ADD',fine,.42,.72);col=g.rgbscale(col,grain)
        local_stone=g.noise(tc.outputs['Object'],g.math('MULTIPLY',p['lod_micro_scale'],64.),2.,.6,0.,p['seed'])
        grit=g.mix(g.math('MULTIPLY',fade,.95),(1.,1.,1.,1),g.mix(g.smooth(local_stone,.38,.62),(.20,.19,.17,1),(1.5,1.45,1.35,1)))
        col=g.vec('MULTIPLY',col,grit)
        if kind=='ROCK':
            b=biome_fields(g,v,p)
            grasscol=g.mix(g.noise(v,9000.,3.,.62,0.,p['seed']),(.016,.033,.006,1),(.045,.075,.015,1))
            forestcol=g.mix(g.noise(v,6000.,3.,.65,0.,p['seed']),(.012,.032,.007,1),(.045,.085,.015,1))
            eco=g.mix(b['forest'],grasscol,forestcol)
            strata=g.math('SINE',g.math('MULTIPLY',g.vec('LENGTH',tc.outputs['Object']),g.math('MULTIPLY',3000.,45.)))
            desertcol=g.mix(g.math('MULTIPLY_ADD',strata,.24,.5),(.16,.072,.028,1),(.40,.24,.115,1))
            eco=g.mix(b['desert'],eco,desertcol)
            rock=g.mix(g.noise(v,14000.,4.,.6,0.,p['seed']),(.095,.082,.066,1),(.31,.28,.22,1))
            eco=g.mix(b['mountain'],eco,rock)
            slope=g.math('SUBTRACT',1.,g.math('ABSOLUTE',g.vec('DOT_PRODUCT',geo.outputs['Normal'],geo.outputs['True Normal'])))
            snow=g.math('MULTIPLY',b['mountain'],g.smooth(b['height'],.00105,.0016))
            eco=g.mix(snow,eco,p['ice_color'])
            col=g.mix(p['biome_enabled'],col,eco)
        ocean=g.mix(g.smooth(field,g.math('SUBTRACT',p['sea_level'],.08),p['sea_level']),g.rgbscale(p['ocean_color'],.4),p['ocean_color'])
        if kind=='ROCK':
            dry=g.math('ADD',g.math('MULTIPLY',dry,g.math('SUBTRACT',1.,p['biome_enabled'])),g.math('MULTIPLY',b['land'],p['biome_enabled']))
            grazing=g.math('POWER',g.math('SUBTRACT',1.,g.math('ABSOLUTE',g.vec('DOT_PRODUCT',normal,geo.outputs['Incoming']))),4.)
            water=g.mix(grazing,g.rgbscale(p['ocean_color'],.7),(.16,.27,.36,1))
            ocean=g.mix(p['biome_enabled'],ocean,water)
        col=g.mix(dry,ocean,col)
        latitude=g.math('ABSOLUTE',z);ice=g.smooth(g.math('ADD',latitude,g.math('MULTIPLY',field,.07)),p['ice'],g.math('ADD',p['ice'],.06))
        ice=g.math('MULTIPLY',ice,g.math('LESS_THAN',p['ice'],.99))
        col=g.mix(ice,col,p['ice_color'])
        physical_color=col
        if kind=='ROCK' and root.get('biome_enabled'):
            forestfloor=ground_texture(g,tc.outputs['Object'],'forrest_ground_01')
            meadowfloor=ground_texture(g,tc.outputs['Object'],'leafy_grass')
            dryrock=ground_texture(g,tc.outputs['Object'],'rock_boulder_dry')
            if forestfloor is not None:
                ground=g.mix(b['forest'],g.vec('MULTIPLY',meadowfloor,(.10,.20,.07)),g.vec('SCALE',forestfloor,scale=.65))
                mottling=g.math('MULTIPLY_ADD',g.noise(v,280000.,2.,.6,0.,p['seed']),.65,.55)
                ground=g.vec('SCALE',ground,scale=mottling)
                strata=g.math('MULTIPLY_ADD',g.math('SINE',g.math('MULTIPLY',b['height'],g.math('MULTIPLY',3000.,300.))),.14,.86)
                sandstone=g.vec('MULTIPLY',dryrock,g.vec('SCALE',(.62,.32,.16),scale=strata))
                granite=g.vec('MULTIPLY',dryrock,(.48,.53,.59)) if root.get('biome_realism') else g.vec('SCALE',dryrock,scale=.55)
                mineral=g.mix(b['desert'],granite,sandstone)
                ground=g.mix(g.math('MAXIMUM',b['mountain'],b['desert']),ground,mineral)
                macro=ground_texture(g,tc.outputs['Object'],'rock_boulder_dry',frequency=15000.)
                macro=g.vec('ADD',g.vec('SCALE',macro,scale=2.),(.5,.5,.5))
                ground=g.vec('MULTIPLY',ground,g.mix(g.math('MAXIMUM',b['mountain'],b['desert']),(1.,1.,1.,1),macro))
                # Keep distant land under the same photographic palette as the
                # near texture, so model fades do not expose a bright flat band.
                distance_weight=g.math('MAXIMUM',fade,.65)
                physical_color=g.mix(g.math('MULTIPLY',distance_weight,dry),physical_color,ground)
                # A forest seen from above resolves to foliage, rather than
                # the colour of its largely hidden soil. Match the geometric
                # canopy/grass proxy once individual instances lose coverage.
                view=g.node('ShaderNodeCameraData')
                distance=g.math('DIVIDE',view.outputs['View Distance'],p['radius'])
                treereach=g.math('MINIMUM',p['biome_range'],p['biome_tree_distance'] if root.get('biome_realism') else g.math('MULTIPLY',p['biome_tree_height'],.45*65.))
                grassreach=g.math('MINIMUM',p['biome_range'],g.math('MULTIPLY',p['biome_grass_height'],600.))
                treetake=g.math('MULTIPLY',b['forest'],g.smooth(distance,g.math('MULTIPLY',treereach,.6),treereach))
                if root.get('biome_realism'):
                    from . import ecology
                    _,coverage=ecology.graph_canopy(g,v,p,b['forest'])
                    treetake=g.math('MULTIPLY',treetake,coverage)
                grasstake=g.math('MULTIPLY',b['grass'],g.smooth(distance,g.math('MULTIPLY',grassreach,.1),g.math('MULTIPLY',grassreach,.5)))
                if root.get('biome_realism'):
                    # Subpixel stems are represented by filtered surface
                    # variation rather than an untextured single green band.
                    grassproxy=g.vec('MULTIPLY',meadowfloor,(.20,.29,.10))
                    grassproxy=g.vec('SCALE',grassproxy,scale=g.math('MULTIPLY_ADD',g.noise(v,60000.,3.,.62,0.,p['seed']),.8,.6))
                    physical_color=g.mix(grasstake,physical_color,grassproxy)
                    physical_color=g.mix(treetake,physical_color,forestcol)
                else:physical_color=g.mix(g.math('MAXIMUM',treetake,grasstake),physical_color,eco)
                radial=g.node('ShaderNodeVectorTransform',vector_type='NORMAL',convert_from='OBJECT',convert_to='WORLD')
                g.put(v,radial.inputs[0])
                slope=g.vec('DOT_PRODUCT',geo.outputs['Normal'],g.vec('NORMALIZE',radial.outputs[0]))
                snow_height=g.smooth(b['mountain_relief'],.44,.72)
                snow_cover=g.math('MULTIPLY',b['mountain'],g.math('MULTIPLY',snow_height,g.smooth(slope,.50,.86)))
                physical_color=g.mix(g.math('MAXIMUM',ice,snow_cover),physical_color,p['ice_color'])
        # Ocean's analytic specular responds to the camera and virtual sun.
        # Geometry Incoming and the half vector are in world space.
        incoming=geo.outputs['Incoming'];half=g.vec('NORMALIZE',g.vec('ADD',incoming,sun_vector(g,p)))
        spec=g.math('POWER',g.math('MAXIMUM',g.vec('DOT_PRODUCT',normal,half),0.),170.)
        spec=g.math('MULTIPLY',spec,g.math('MULTIPLY',p['ocean_glint'],g.math('SUBTRACT',1.,dry)))
        # Cloud occlusion sampled along the shared sunlight direction. This is a
        # texture-space shadow approximation, so it behaves alike in both engines.
        cv=g.vec('NORMALIZE',g.vec('ADD',v,g.vec('SCALE',local_sun(g,p),scale=.018)))
        shadow,cw=cloud_field(g,cv,p)
        light=g.math('MULTIPLY',light,g.math('SUBTRACT',1.,g.math('MULTIPLY',shadow,.35)))
        col=g.rgbscale(col,light);col=g.vec('ADD',col,g.rgbscale((.9,.80,.62),g.math('MULTIPLY',spec,day)))
        # Network follows land masses; city roads are spherical, without UV seams.
        net=g.node('ShaderNodeTexVoronoi','Metropolitan network',feature='DISTANCE_TO_EDGE');g.put(v,net.inputs['Vector']);net.inputs['Scale'].default_value=120.
        roads=g.math('SUBTRACT',1.,g.smooth(net.outputs['Distance'],.008,.025))
        urban=g.smooth(g.noise(v,45.,3.,.7,0.,p['seed']),.56,.65)
        cities=g.math('MULTIPLY',g.math('MULTIPLY',urban,roads),g.math('MULTIPLY',dry,p['city_lights']))
        cities=g.math('MULTIPLY',cities,g.math('SUBTRACT',1.,g.smooth(dot,-.13,.20)))
        col=g.vec('ADD',col,g.rgbscale((1.,.48,.085),g.math('MULTIPLY',cities,3.)))
        fiss=g.node('ShaderNodeTexVoronoi','Tectonic fissures',feature='DISTANCE_TO_EDGE');g.put(g.vec('ADD',v,g.vec('SCALE',v,scale=g.noise(v,6.,3.))),fiss.inputs['Vector']);fiss.inputs['Scale'].default_value=4.5
        lava=g.math('MULTIPLY',g.math('SUBTRACT',1.,g.smooth(fiss.outputs['Distance'],.012,.048)),p['lava'])
        lava=g.math('MULTIPLY',lava,g.smooth(field,.34,.54))
        col=g.vec('ADD',col,g.rgbscale((1.,.13,.002),g.math('MULTIPLY',lava,4.)))
        haze=g.math('MULTIPLY',p['haze'],g.math('MULTIPLY',day,g.math('POWER',g.math('SUBTRACT',1.,g.math('ABSOLUTE',g.vec('DOT_PRODUCT',normal,incoming))),2.)))
        col=g.mix(haze,col,g.rgbscale(p['atmosphere_color'],.5))
        crevice=g.smooth(g.noise(v,p['lod_micro_scale'],g.math('MULTIPLY',fade,4.),.55,0.,p['seed']),.3,.5)
        col=g.rgbscale(col,g.math('SUBTRACT',1.,g.math('MULTIPLY',g.math('SUBTRACT',1.,crevice),g.math('MULTIPLY',fade,p['lod_ao']))))
        col=aerial_perspective(g,col,p,origin)
        if kind=='ROCK':
            bsdf=g.node('ShaderNodeBsdfPrincipled','Physical terrain and water')
            wave_attr=g.node('ShaderNodeAttribute','Evaluated geometric wave');wave_attr.attribute_name='op_wave_offset'
            crest=g.vec('DOT_PRODUCT',wave_attr.outputs['Vector'],v)
            foam=g.math('MULTIPLY',g.smooth(crest,g.math('MULTIPLY',p['biome_wave_height'],.95),g.math('MULTIPLY',p['biome_wave_height'],1.45)),g.math('SUBTRACT',1.,dry))
            foam=g.math('MULTIPLY',foam,g.smooth(g.noise(tc.outputs['Object'],g.math('MULTIPLY',3000.,1000.),3.,.6),.44,.64))
            basecolor=g.mix(dry,g.mix(foam,(.003,.022,.026,1),(.65,.72,.73,1)),physical_color)
            g.put(basecolor,bsdf.inputs['Base Color']);g.put(g.math('ADD',g.math('MULTIPLY_ADD',dry,.82,.055),g.math('MULTIPLY',foam,.45)),bsdf.inputs['Roughness'])
            g.put(g.math('MULTIPLY_ADD',dry,.117,1.333),bsdf.inputs['IOR'])
            if root.get('biome_enabled'):
                floorheight=ground_texture(g,tc.outputs['Object'],'leafy_grass','height')
                if floorheight is not None:
                    rockheight=ground_texture(g,tc.outputs['Object'],'rock_boulder_dry','height')
                    floorheight=g.mix(g.math('MAXIMUM',b['mountain'],b['desert']),floorheight,rockheight)
                    bump=g.node('ShaderNodeBump','Photographed ground microrelief')
                    g.put(floorheight,bump.inputs['Height']);g.put(g.math('MULTIPLY',p['radius'],.000000003),bump.inputs['Distance'])
                    g.put(g.math('MULTIPLY',fade,dry),bump.inputs['Strength'])
                    drift=g.vec('ADD',tc.outputs['Object'],g.vec('SCALE',(.7,.3,.2),scale=g.math('MULTIPLY',p['biome_time'],.00000003)))
                    micro=g.noise(drift,g.math('MULTIPLY',10000.,1000.),3.,.6)
                    ripple=g.node('ShaderNodeBump','Small water ripples above geometric swells')
                    g.put(micro,ripple.inputs['Height']);g.put(g.math('MULTIPLY',p['radius'],.000000002),ripple.inputs['Distance'])
                    g.put(g.math('SUBTRACT',1.,dry),ripple.inputs['Strength']);g.put(bump.outputs['Normal'],ripple.inputs['Normal']);g.put(ripple.outputs['Normal'],bsdf.inputs['Normal'])
            fog,opacity,inside=atmosphere_path(g,p,True,origin)
            fogmix=g.node('ShaderNodeMixShader','Physical surface with shared aerial haze')
            g.put(g.math('MULTIPLY',inside,opacity),fogmix.inputs[0]);g.put(bsdf.outputs[0],fogmix.inputs[1]);g.put(emission(g,fog),fogmix.inputs[2])
            mode=g.node('ShaderNodeMixShader','Orbital analytic / living PBR surface')
            g.put(p['biome_enabled'],mode.inputs[0]);g.put(emission(g,col),mode.inputs[1]);g.put(fogmix.outputs[0],mode.inputs[2]);output(g,mode.outputs[0])
        else:output(g,emission(g,col))
        return m
    output(g,emission(g,g.rgbscale(col,light)));return m

def clouds(root,t):
    m,g=material(root.name+' Â· Clouds');p=params(g,t);tc=g.node('ShaderNodeTexCoord')
    v=g.vec('NORMALIZE',tc.outputs['Object']);alpha,wisps=cloud_field(g,v,p)
    if root.get('biome_enabled'):
        root['op_living_cloud_visibility']=root.get('op_living_cloud_visibility',1.)
        visibility=g.node('ShaderNodeValue','Atmospheric entry cloud fade');drive(visibility.outputs[0],root,'op_living_cloud_visibility')
        alpha=g.math('MULTIPLY',alpha,visibility.outputs[0])
    geo=g.node('ShaderNodeNewGeometry');li,dot,day=lighting(g,geo.outputs['Normal'],p,.13)
    col=g.rgbscale(p['cloud_color'],g.math('MULTIPLY',li,g.math('MULTIPLY_ADD',wisps,.23,.78)))
    col=aerial_perspective(g,col,p)
    # Interior cloud views need the far boundary's underside rather than front faces.
    info=g.node('ShaderNodeObjectInfo');cam=g.node('ShaderNodeCameraData')
    origin=g.vec('ADD',g.vec('SUBTRACT',geo.outputs['Position'],info.outputs['Location']),g.vec('SCALE',geo.outputs['Incoming'],scale=cam.outputs['View Distance']))
    cloud_radius=g.math('MULTIPLY',p['radius'],g.math('ADD',1.,g.math('ADD',p['cloud_height'],g.math('MULTIPLY',p['cloud_depth'],.5))))
    under=g.math('LESS_THAN',g.vec('LENGTH',origin),cloud_radius)
    front=g.math('SUBTRACT',1.,geo.outputs['Backfacing'])
    facing=g.math('ADD',g.math('MULTIPLY',under,geo.outputs['Backfacing']),g.math('MULTIPLY',g.math('SUBTRACT',1.,under),front))
    facing=g.math('ADD',g.math('MULTIPLY',p['lod_enabled'],facing),g.math('MULTIPLY',g.math('SUBTRACT',1.,p['lod_enabled']),front))
    soften=g.smooth(g.math('DIVIDE',cam.outputs['View Distance'],p['radius']),0.,.0004)
    alpha=g.math('MULTIPLY',alpha,g.math('ADD',g.math('SUBTRACT',1.,p['lod_enabled']),g.math('MULTIPLY',p['lod_enabled'],soften)))
    return add_transparency(g,m,col,alpha,facing=facing)

def atmosphere(root,t,kind):
    m,g=material(root.name+' Â· Atmosphere');p=params(g,t);geo=g.node('ShaderNodeNewGeometry')
    tc=g.node('ShaderNodeTexCoord');v=g.vec('NORMALIZE',tc.outputs['Object'])
    mu=g.math('ABSOLUTE',g.vec('DOT_PRODUCT',geo.outputs['Normal'],geo.outputs['Incoming']))
    # Analytic optical path through a spherical shell. Opacity vanishes smoothly
    # at the outer silhouette and peaks near the surface's horizon.
    radius=g.math('ADD',1.,p['atmosphere_height']);r2=g.math('MULTIPLY',radius,radius)
    b2=g.math('MULTIPLY',r2,g.math('SUBTRACT',1.,g.math('MULTIPLY',mu,mu)))
    outer=g.math('SQRT',g.math('MAXIMUM',g.math('SUBTRACT',r2,b2),0.))
    inner=g.math('SQRT',g.math('MAXIMUM',g.math('SUBTRACT',1.,b2),0.))
    norm=g.math('SQRT',g.math('SUBTRACT',r2,1.))
    rim=g.math('DIVIDE',g.math('SUBTRACT',outer,inner),norm)
    rim=g.math('POWER',g.math('MAXIMUM',rim,0.),1.35)
    li,dot,day=lighting(g,geo.outputs['Normal'],p,.25)
    lit=g.math('ADD',.025,g.math('MULTIPLY',day,.975)) if kind!='STAR' else 1.
    intensity=g.math('MULTIPLY',g.math('MULTIPLY',rim,p['atmosphere']),lit)
    col=p['atmosphere_color']
    if kind=='STAR':return add_transparency(g,m,col,intensity,False)
    fog,alpha,inside=atmosphere_path(g,p)
    front=g.math('SUBTRACT',1.,geo.outputs['Backfacing'])
    newface=g.math('ADD',g.math('MULTIPLY',inside,geo.outputs['Backfacing']),g.math('MULTIPLY',g.math('SUBTRACT',1.,inside),front))
    facing=g.math('ADD',g.math('MULTIPLY',p['lod_enabled'],newface),g.math('MULTIPLY',g.math('SUBTRACT',1.,p['lod_enabled']),front))
    intensity=g.math('ADD',g.math('MULTIPLY',p['lod_enabled'],alpha),g.math('MULTIPLY',g.math('SUBTRACT',1.,p['lod_enabled']),intensity))
    col=g.mix(p['lod_enabled'],col,fog)
    sky_path=Path(__file__).parent/'assets/ground/sky.hdr'
    if root.get('biome_enabled') and sky_path.exists():
        image=bpy.data.images.load(str(sky_path),check_existing=True)
        if not image.packed_file:image.pack()
        cam=g.node('ShaderNodeCameraData');info=g.node('ShaderNodeObjectInfo')
        camera_position=g.vec('ADD',g.vec('SUBTRACT',geo.outputs['Position'],info.outputs['Location']),g.vec('SCALE',geo.outputs['Incoming'],scale=cam.outputs['View Distance']))
        up=g.vec('NORMALIZE',camera_position);east=g.vec('NORMALIZE',g.vec('CROSS_PRODUCT',(0.,0.,1.),up));north=g.vec('CROSS_PRODUCT',up,east)
        ray=g.vec('SCALE',geo.outputs['Incoming'],scale=-1.)
        direction=g.combine(g.vec('DOT_PRODUCT',ray,east),g.vec('DOT_PRODUCT',ray,north),g.vec('DOT_PRODUCT',ray,up))
        env=g.node('ShaderNodeTexEnvironment','CC0 photographic sky');env.image=image;g.put(direction,env.inputs['Vector'])
        weight=g.math('MULTIPLY',inside,p['biome_enabled'])
        col=g.mix(weight,col,g.rgbscale(env.outputs['Color'],.7))
        intensity=g.math('ADD',g.math('MULTIPLY',intensity,g.math('SUBTRACT',1.,weight)),weight)
    return add_transparency(g,m,col,intensity,False,facing=facing)

def rings(root,t):
    m,g=material(root.name+' Â· Rings');p=params(g,t);tc=g.node('ShaderNodeTexCoord');pos=tc.outputs['Object']
    radial=g.vec('LENGTH',pos);micro=g.noise(g.combine(radial,0.,0.),210.,2.,.65,0.,p['ring_seed'])
    broad=g.noise(g.combine(radial,0.,0.),15.,2.,.65,0.,p['ring_seed'])
    striation=g.math('MULTIPLY',micro,g.math('MULTIPLY_ADD',broad,.7,.3))
    inner=g.smooth(radial,p['ring_inner'],g.math('ADD',p['ring_inner'],.04))
    outer=g.math('SUBTRACT',1.,g.smooth(radial,g.math('SUBTRACT',p['ring_outer'],.05),p['ring_outer']))
    gap=g.math('SUBTRACT',1.,g.math('MULTIPLY',g.smooth(radial,1.94,1.96),g.math('SUBTRACT',1.,g.smooth(radial,2.03,2.05))))
    alpha=g.math('MULTIPLY',g.math('MULTIPLY',inner,outer),g.math('MULTIPLY',striation,g.math('MULTIPLY',p['ring_density'],gap)))
    alpha=g.math('MULTIPLY',alpha,p['rings'])
    # Analytic occlusion by the sphere along the shared sun direction.
    # Object position is normalized to planet radius, rotate normal-space vector to world.
    vt=g.node('ShaderNodeVectorTransform',vector_type='VECTOR',convert_from='OBJECT',convert_to='WORLD');g.put(pos,vt.inputs[0])
    wp=g.vec('SCALE',vt.outputs[0],scale=g.math('DIVIDE',1.,p['radius']))
    sd=sun_vector(g,p);along=g.vec('DOT_PRODUCT',wp,sd)
    dist2=g.math('SUBTRACT',g.vec('DOT_PRODUCT',wp,wp),g.math('MULTIPLY',along,along))
    shadow=g.math('MULTIPLY',g.math('LESS_THAN',along,0.),g.math('SUBTRACT',1.,g.smooth(dist2,.98,1.04)))
    col=g.rgbscale(p['ring_color'],g.math('MULTIPLY',g.math('MULTIPLY_ADD',striation,.7,.35),g.math('SUBTRACT',1.,g.math('MULTIPLY',shadow,.98))))
    # Rings are intentionally double-sided: reverse-facing faces are needed under tilt.
    try:m.surface_render_method='BLENDED'
    except (AttributeError,TypeError):pass
    tr=g.node('ShaderNodeBsdfTransparent');em=emission(g,col);mx=g.node('ShaderNodeMixShader');g.put(alpha,mx.inputs[0]);g.put(tr.outputs[0],mx.inputs[1]);g.put(em,mx.inputs[2]);output(g,mx.outputs[0]);return m

def core(root,t):
    m,g=material(root.name+' Â· Molten core');p=params(g,t);tc=g.node('ShaderNodeTexCoord')
    f=g.noise(tc.outputs['Object'],9.,5.,.7,3.,p['seed'])
    col=g.mix(g.smooth(f,.25,.7),(.28,.008,.0002,1),(1.,.28,.008,1))
    output(g,emission(g,g.rgbscale(col,1.7)));return m
