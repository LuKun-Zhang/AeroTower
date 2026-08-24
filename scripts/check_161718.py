import json
d = json.load(open('demo/public/terminal_layout.json','r',encoding='utf-8'))
for g in d['gates']:
    if g['name'] in ('矩形 16', '矩形 17', '矩形 18'):
        print(f'{g["name"]}: cx={g["x"]+g["w"]/2:.1f} cy={g["y"]+g["h"]/2:.1f} ref={g["attach"]["ref"]}')
