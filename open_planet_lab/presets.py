# SPDX-License-Identifier: GPL-3.0-or-later
"""Original procedural worlds. No commercial assets or node graphs."""
BASE = dict(seed=7., radius=2., terrain_scale=2.4, detail=5., sea_level=.51,
            relief=.065, crater_amount=0., crater_scale=14., ice=.79,
            cloud_coverage=.39, cloud_scale=5., cloud_height=.009,
            cloud_depth=.004, cloud_rotation=0., atmosphere=.48,
            atmosphere_height=.027, haze=.11, ocean_glint=.55,
            city_lights=0., lava=0., band_scale=17., storm=.5,
            sun_azimuth=-35., sun_elevation=28., exposure=1., night_fill=.006,
            rings=0., ring_inner=1.48, ring_outer=2.35, ring_density=.78,
            ring_tilt=22., ring_seed=3., star_strength=2.8,
            land_color=(.028,.085,.018,1), high_color=(.25,.17,.075,1),
            ocean_color=(.005,.028,.085,1), ice_color=(.72,.86,.92,1),
            atmosphere_color=(.065,.31,1.,1), cloud_color=(.86,.91,1.,1),
            ring_color=(.58,.43,.24,1), star_color=(1.,.24,.025,1))

PRESETS = {
 'TERRA': ('Terra Â· Ocean & Continents', 'ROCK', dict(city_lights=.28)),
 'ARCHIPELAGO': ('Pelagic Â· Island World', 'ROCK', dict(seed=29., sea_level=.59,
    terrain_scale=3.8, relief=.035, ocean_color=(.004,.105,.16,1), cloud_coverage=.38)),
 'DESERT': ('Ares Â· Desert', 'ROCK', dict(seed=17., sea_level=.25, cloud_coverage=0.,
    relief=.11, ice=.94, atmosphere=.18, atmosphere_color=(1.,.28,.07,1),
    land_color=(.30,.095,.032,1),high_color=(.67,.34,.12,1), crater_amount=.35)),
 'MOON': ('Selene Â· Cratered Moon', 'ROCK', dict(seed=19., sea_level=0.,
    atmosphere=0.,haze=0.,cloud_coverage=0., relief=.04, crater_amount=1.,
    crater_scale=9., ice=1., land_color=(.22,.21,.20,1),high_color=(.49,.47,.43,1))),
 'ICE': ('Borealis Â· Ice World', 'ROCK', dict(seed=37.,sea_level=.39,ice=.23,
    relief=.07, cloud_coverage=.16, atmosphere=.24,
    land_color=(.16,.34,.43,1),high_color=(.69,.86,.91,1),ocean_color=(.014,.035,.08,1))),
 'LAVA': ('Vulcan Â· Volcanic World', 'ROCK', dict(seed=43.,sea_level=0., ice=1.,
    lava=1.,relief=.095, cloud_coverage=.15,atmosphere=.33,
    atmosphere_color=(1.,.055,.002,1),cloud_color=(.16,.11,.09,1),
    land_color=(.022,.014,.012,1),high_color=(.14,.075,.045,1))),
 'CITY': ('Ecumenopolis Â· City World', 'ROCK', dict(seed=13.,sea_level=.25,
    relief=.022,cloud_coverage=.24,city_lights=1.,
    land_color=(.14,.15,.16,1),high_color=(.31,.32,.33,1))),
 'BROKEN': ('Rupture Â· Shattered World', 'BROKEN', dict(seed=11.,sea_level=0.,
    ice=1.,lava=.2,cloud_coverage=0.,atmosphere=0.,atmosphere_color=(1.,.12,.01,1),
    relief=.15, land_color=(.06,.035,.023,1),high_color=(.26,.14,.065,1))),
 'GAS': ('Aureole Â· Ringed Gas Giant', 'GAS', dict(seed=23.,cloud_coverage=0.,
    rings=1., relief=0.,ice=1.,atmosphere=.27,atmosphere_height=.016,
    atmosphere_color=(.8,.47,.18,1),land_color=(.34,.16,.075,1),
    high_color=(.83,.66,.37,1),ocean_color=(.13,.055,.028,1))),
 'NEPTUNE': ('Nereid Â· Blue Gas Giant', 'GAS', dict(seed=41., cloud_coverage=0.,
    relief=0.,ice=1.,atmosphere=.45,band_scale=22.,
    land_color=(.013,.07,.32,1),high_color=(.14,.49,.83,1),ocean_color=(.005,.02,.12,1))),
 'STAR': ('Helios Â· Star', 'STAR', dict(cloud_coverage=0.,relief=.012,
    atmosphere=.7,atmosphere_height=.065,haze=0., atmosphere_color=(1.,.10,.005,1))),
}

LABELS = {
 'seed':'World seed', 'radius':'Radius', 'terrain_scale':'Continent scale',
 'detail':'Surface detail','sea_level':'Ocean level','relief':'Terrain relief',
 'crater_amount':'Crater strength','crater_scale':'Crater frequency','ice':'Ice latitude',
 'cloud_coverage':'Cloud coverage','cloud_scale':'Cloud scale',
 'cloud_height':'Cloud altitude','cloud_depth':'Cloud depth','cloud_rotation':'Cloud drift',
 'atmosphere':'Atmosphere strength','atmosphere_height':'Atmosphere height','haze':'Surface haze',
 'ocean_glint':'Ocean glint','city_lights':'City lights','lava':'Lava fissures',
 'band_scale':'Gas bands','storm':'Storm turbulence', 'sun_azimuth':'Sun azimuth',
 'sun_elevation':'Sun elevation','exposure':'Sun intensity','night_fill':'Night fill',
 'rings':'Enable rings','ring_inner':'Ring inner radius','ring_outer':'Ring outer radius',
 'ring_density':'Ring density','ring_tilt':'Ring tilt','ring_seed':'Ring variation',
 'star_strength':'Star emission','land_color':'Lowland','high_color':'Highland',
 'ocean_color':'Ocean','ice_color':'Ice','atmosphere_color':'Atmosphere',
 'cloud_color':'Clouds','ring_color':'Rings','star_color':'Star',
}

RANGES = {key:(0.,1.) for key in BASE if not key.endswith('_color')}
RANGES.update(seed=(0.,1000.),radius=(.1,100000000.),terrain_scale=(.2,12.),detail=(0.,12.),
    relief=(0.,.4),crater_scale=(2.,50.),cloud_scale=(.3,20.),cloud_height=(.005,.15),
    cloud_depth=(0.,.06),cloud_rotation=(-360.,360.),atmosphere=(0.,2.),
    atmosphere_height=(.004,.15),band_scale=(1.,80.),sun_azimuth=(-180.,180.),
    sun_elevation=(-89.,89.),exposure=(0.,5.),night_fill=(0.,.2),ring_inner=(1.08,3.),
    ring_outer=(1.1,5.),ring_tilt=(-80.,80.),ring_seed=(0.,100.),star_strength=(.1,15.))

BASE.update(lod_enabled=False,lod_auto=True,lod_budget=60000,lod_pixels=4.,
    lod_near=.004,lod_far=.25,lod_max_depth=18,lod_micro_height=.00010,
    lod_micro_scale=1800.,lod_micro_normal=.35,lod_ao=.18)
LABELS.update(lod_enabled='Camera LOD',lod_auto='Live camera updates',lod_budget='Triangle budget',
    lod_pixels='Target edge pixels',lod_near='Full detail distance / radius',lod_far='Detail fade distance / radius',
    lod_max_depth='Maximum refinement depth',lod_micro_height='Local terrain height / radius',
    lod_micro_scale='Local terrain frequency',lod_micro_normal='Local normal detail',lod_ao='Local crevice shading')
RANGES.update(lod_enabled=(0,1),lod_auto=(0,1),lod_budget=(2048,500000),lod_pixels=(.5,32.),
    lod_near=(.000001,2.),lod_far=(.00001,10.),lod_max_depth=(4,24),
    lod_micro_height=(0.,.002),lod_micro_scale=(100.,100000.),lod_micro_normal=(0.,2.),lod_ao=(0.,1.))

# Surface ecology is opt-in, so existing orbital/entry assets retain their look.
BASE.update(biome_enabled=False,biome_mode=0,biome_relief=.006,biome_mountains=.0008,
    biome_canyons=.0004,biome_tree_height=.0000035,biome_grass_height=.00000011,
    biome_rock_size=.0000003,biome_fern_height=.00000018,biome_range=.00035,biome_density=.8,
    biome_budget=600000,biome_instances=6000,biome_wave_height=.0000006,
    biome_wave_length=.000012,biome_time=0.,biome_shadow_distance=.004,biome_view_distance=.001)
LABELS.update(biome_enabled='Living surface geometry',biome_mode='Biome mode',
    biome_relief='Continental elevation / radius',biome_mountains='Mountain height / radius',
    biome_canyons='Canyon depth / radius',biome_tree_height='Tree height / radius',
    biome_grass_height='Grass height / radius',biome_rock_size='Rock size / radius',biome_fern_height='Undergrowth height / radius',
    biome_range='Scatter distance / radius',biome_density='Vegetation density',
    biome_budget='Scatter triangle budget',biome_instances='Maximum instances',
    biome_wave_height='Wave amplitude / radius',biome_wave_length='Wavelength / radius',biome_time='Water time (seconds)',biome_shadow_distance='Shadow distance / radius',biome_view_distance='Minimum view distance / radius')
RANGES.update(biome_enabled=(0,1),biome_mode=(0,5),biome_relief=(0.,.03),biome_mountains=(0.,.005),
    biome_canyons=(0.,.002),biome_tree_height=(.0000001,.0001),biome_grass_height=(.00000001,.000005),
    biome_rock_size=(.00000001,.00001),biome_fern_height=(.00000001,.000005),biome_range=(.000005,.01),biome_density=(0.,1.),
    biome_budget=(1000,5000000),biome_instances=(1,120000),biome_wave_height=(0.,.0001),
    biome_wave_length=(.0000005,.001),biome_time=(-100000.,100000.),biome_shadow_distance=(.00001,.1),biome_view_distance=(.00001,1.))

BASE.update(biome_realism=False,biome_region_strength=1.,biome_transition=.22,biome_tree_distance=.00018)
LABELS.update(biome_realism='Coherent terrain and habitat',biome_region_strength='Measured terrain height scale',
    biome_transition='Detail transition width',biome_tree_distance='Individual tree distance / radius')
RANGES.update(biome_realism=(0,1),biome_region_strength=(.1,3.),biome_transition=(.05,.5),biome_tree_distance=(.00001,.002))
