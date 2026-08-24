import json

with open('demo/public/terminal_layout.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

gates = d['gates']
print(f'Total gates: {len(gates)}')
print(f'Rect: {len([g for g in gates if g["type"]=="rect"])}')
print(f'Arrows: {len([g for g in gates if g["type"]!="rect"])}')

# Check duplicates
names = {}
for g in gates:
    n = g['name']
    names[n] = names.get(n, 0) + 1
dups = {k: v for k, v in names.items() if v > 1}
print(f'\nDuplicate names ({len(dups)}):')
for k, v in sorted(dups.items()):
    print(f'  {k}: {v}x')

# Find 矩形 56
for g in gates:
    if '56' in g.get('name', ''):
        ref = g.get('attach', {}).get('ref', '?')
        print(f'\n{g["name"]}: x={g["x"]} y={g["y"]} w={g["w"]} h={g["h"]} ref="{ref}" type={g["type"]}')

# Find gates around x=418 y=350 (矩形56 area)
print('\n\nGates near x=410-440 y=345-360:')
for g in gates:
    cx = g['x'] + g['w'] / 2
    cy = g['y'] + g['h'] / 2
    if 410 <= cx <= 440 and 345 <= cy <= 360:
        ref = g.get('attach', {}).get('ref', '?')
        print(f'  {g["name"]}: cx={cx:.1f} cy={cy:.1f} ref="{ref}" type={g["type"]}')
