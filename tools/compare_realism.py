from pathlib import Path
import json,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/planets/realism'
canvas=Image.new('RGB',(1920,584),(16,21,28));draw=ImageDraw.Draw(canvas);metrics={}
for col,name in enumerate(('Forest','Grassland','Alpine','Desert')):
    a=np.asarray(Image.open(OUT/(name.lower()+'_eevee.png')).convert('RGB'),dtype=np.float32)/255
    b=np.asarray(Image.open(OUT/(name.lower()+'_cycles.png')).convert('RGB'),dtype=np.float32)/255
    delta=np.abs(a-b);h,w=delta.shape[:2]
    metrics[name]=dict(mean_display_rgb_percent=float(delta.mean()*100),p95_channel_difference_percent=float(np.percentile(delta,95)*100),p99_channel_difference_percent=float(np.percentile(delta,99)*100),
        foreground_mean_percent=float(delta[int(h*.45):].mean()*100),center_mean_percent=float(delta[int(h*.2):int(h*.8),int(w*.2):int(w*.8)].mean()*100),resolution=[w,h])
    for row,label in enumerate(('eevee','cycles')):
        image=Image.open(OUT/(name.lower()+'_'+label+'.png')).convert('RGB').resize((480,270),Image.Resampling.LANCZOS)
        canvas.paste(image,(col*480,row*292+22));draw.text((col*480+8,row*292+5),name+' | '+label.upper(),fill=(240,244,249))
(OUT/'realism_metrics.json').write_text(json.dumps(metrics,indent=2));canvas.save(OUT/'realism_comparison.jpg',quality=93)
print(json.dumps(metrics,indent=2))
