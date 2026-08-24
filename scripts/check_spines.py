import json

d = json.load(open('demo/public/terminal_layout.json', 'r', encoding='utf-8'))
spines = ['矩形 5','矩形 6','矩形 7','矩形 8','矩形 40','矩形 9','矩形 11','矩形 12','矩形 13']

unmatched = []
for g in d['gates']:
    if g['type'] != 'rect':
        continue
    ref = g.get('attach', {}).get('ref', '')
    matched = any(s in ref for s in spines)
    if not matched:
        cx = g['x'] + g['w'] / 2
        cy = g['y'] + g['h'] / 2
        unmatched.append((g['name'], cx, cy, ref))

print(f'Unmatched rect gates: {len(unmatched)}')
for name, cx, cy, ref in unmatched:
    print(f'  {name}: cx={cx:.1f} cy={cy:.1f} ref="{ref}"')
