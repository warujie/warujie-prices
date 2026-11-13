import json, io, time, urllib.request, os
from PIL import Image, ImageDraw, ImageFont
T = json.load(open('probe/targets.json'))
os.makedirs('probe_out/crops', exist_ok=True)
font = ImageFont.load_default(size=22)
strips = []
for t in T:
    try:
        req = urllib.request.Request(t['img'].split('?')[0], headers={'User-Agent': 'WarujieProbe/1.0 (+https://warujie.jp)'})
        im = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=60).read())).convert('RGB')
    except Exception as e:
        print('error', t['label'], e); continue
    time.sleep(0.15)
    W, H = im.size
    top = im.crop((0, 0, W, int(H * 0.12))).resize((900, int(H * 0.12 * 900 / W)))
    s = Image.new('RGB', (900, top.size[1] + 34), 'white')
    ImageDraw.Draw(s).text((6, 4), t['label'], fill='black', font=font)
    s.paste(top, (0, 34)); strips.append(s)
k = 0
while strips:
    part, strips = strips[:8], strips[8:]
    out = Image.new('RGB', (900, sum(p.size[1] + 6 for p in part)), (80, 80, 80))
    y = 0
    for p in part:
        out.paste(p, (0, y)); y += p.size[1] + 6
    out.save(f'probe_out/crops/sheet{k:02d}.jpg', quality=88); k += 1
print('sheets', k)
