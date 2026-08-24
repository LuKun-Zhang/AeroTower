import json

d = json.load(open('demo/public/terminal_layout.json', 'r', encoding='utf-8'))

gates = d['gates']
t1cx = 154    # T1 center
t2cx = 461    # T2 center

# Find gates with ref "航站楼1" or "航站楼2"
for g in gates:
    ref = g.get('attach', {}).get('ref', '')
    if ref in ('航站楼1', '航站楼2') and g['type'] == 'rect':
        cx = g['x'] + g['w'] / 2
        cy = g['y'] + g['h'] / 2
        print(f'{g["name"]}: cx={cx:.1f} cy={cy:.1f} ref="{ref}" rot={g.get("rot",0)}')
