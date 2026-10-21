"""Encode a one-second title card followed by a 24-second continuous descent."""
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/planets/beta'
REPO = ROOT
MEDIA = REPO / 'docs/media'
MEDIA.mkdir(parents=True, exist_ok=True)
title = Image.new('RGB', (1280, 720), (14, 19, 28))
draw = ImageDraw.Draw(title)
font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 58)
small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 31)
draw.text((640, 305), 'Open Planet Designer', anchor='mm', font=font, fill=(241, 244, 248))
draw.text((640, 389), 'Beta Demo', anchor='mm', font=small, fill=(177, 193, 210))
title.save(OUT / 'intro.png')
shots = ['descent']
for shot in shots:
    frames = sorted((OUT / shot).glob('frame_*.png'))
    assert len(frames) == 576, (shot, len(frames))
    for index, path in enumerate(frames, 1):
        assert path.name == 'frame_%04d.png' % index
        with Image.open(path) as image:
            assert image.size == (1280, 720)
movie = MEDIA / 'open-planet-designer-beta-demo.mp4'
command = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-loop', '1', '-framerate', '24', '-t', '1', '-i', str(OUT / 'intro.png')]
for shot in shots:
    command += ['-framerate', '24', '-start_number', '1', '-i', str(OUT / shot / 'frame_%04d.png')]
command += ['-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]',
            '-map', '[v]', '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-maxrate', '2800k', '-bufsize', '4000k', '-r', '24', '-an',
            '-movflags', '+faststart', str(movie)]
subprocess.run(command, check=True)
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-ss', '23', '-i', str(movie), '-frames:v', '1', '-update', '1', str(MEDIA / 'beta-demo-poster.jpg')], check=True)
# A small animated preview gives GitHub's README a playable-looking entry point;
# the linked H.264 file retains the requested full resolution and frame rate.
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-ss', '1', '-i', str(movie),
                '-filter_complex', 'fps=4,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4',
                '-loop', '0', str(MEDIA / 'beta-demo-preview.gif')], check=True)
probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,duration:format=duration,size',
        '-of', 'json', str(movie)], text=True))
stream = probe['streams'][0]
assert (stream['width'], stream['height']) == (1280, 720)
assert stream['r_frame_rate'] == '24/1' and stream['avg_frame_rate'] == '24/1'
assert int(stream['nb_read_frames']) == 600
probe['rendering'] = {'engine': 'Eevee', 'samples': 24, 'title_seconds': 1, 'shots': shots,
                      'descent_seconds': 24, 'cached_route_geometry': True, 'audio': False}
(MEDIA / 'demo-verification.json').write_text(json.dumps(probe, indent=2))
shutil.copyfile(movie, REPO / 'dist' / movie.name)
print(json.dumps(probe, indent=2))
