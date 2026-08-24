import json

d = json.load(open('demo/public/terminal_layout.json', 'r', encoding='utf-8'))
print('Top keys:', list(d.keys()))

# T1 is at approx x=65, y=291, w=178, h=57 and T2 at x=395, y=270
# Let me use hard-coded values from the Vue component
t1 = {'x': 65, 'w': 178}
t2 = {'x': 395}

allGates = d['gates']
t1_entries = [g for g in allGates if g.get('gate_dir') == 'entry' and g['x'] < (t1['x'] + t1['w'] + 80)]
t2_entries = [g for g in allGates if g.get('gate_dir') == 'entry' and g['x'] > (t2['x'] - 80)]
t1_exits  = [g for g in allGates if g.get('gate_dir') == 'exit'  and g['x'] < (t1['x'] + t1['w'] + 80)]
t2_exits  = [g for g in allGates if g.get('gate_dir') == 'exit'  and g['x'] > (t2['x'] - 80)]

t1_refs = ['矩形 5', '矩形 6', '矩形 7', '矩形 8', '矩形 40', '航站楼1']
t2_refs = ['矩形 9', '矩形 11', '矩形 12', '矩形 13', '航站楼2']

t1_rect = [g for g in allGates if g['type'] == 'rect' and any(r in g.get('attach', {}).get('ref', '') for r in t1_refs)]
t2_rect = [g for g in allGates if g['type'] == 'rect' and any(r in g.get('attach', {}).get('ref', '') for r in t2_refs)]

print(f'\nT1 entries: {len(t1_entries)}, exits: {len(t1_exits)}, rect gates: {len(t1_rect)}')
print(f'T1 routes: {len(t1_entries)} x {len(t1_rect)} = {len(t1_entries)*len(t1_rect)} corridors')
print(f'T1 exit rays: {len(t1_rect)}')

for g in t1_entries:
    print(f'  entry: {g["name"]} x={g["x"]:.1f} y={g["y"]:.1f}')
for g in t1_exits:
    print(f'  exit:  {g["name"]} x={g["x"]:.1f} y={g["y"]:.1f}')

print(f'\nT2 entries: {len(t2_entries)}, exits: {len(t2_exits)}, rect gates: {len(t2_rect)}')
print(f'T2 routes: {len(t2_entries)} x {len(t2_rect)} = {len(t2_entries)*len(t2_rect)} corridors')
print(f'T2 exit rays: {len(t2_rect)}')

for g in t2_entries:
    print(f'  entry: {g["name"]} x={g["x"]:.1f} y={g["y"]:.1f}')
for g in t2_exits:
    print(f'  exit:  {g["name"]} x={g["x"]:.1f} y={g["y"]:.1f}')

print('\nT1 rect gates by pier:')
for ref in t1_refs:
    gates = [g for g in t1_rect if ref in g.get('attach', {}).get('ref', '')]
    with_rot = [g for g in gates if g.get('rot', 0) != 0]
    rot_vals = [g['rot'] for g in with_rot]
    print(f'  {ref}: {len(gates)} gates, {len(with_rot)} rotated {rot_vals}')

print('\nT2 rect gates by pier:')
for ref in t2_refs:
    gates = [g for g in t2_rect if ref in g.get('attach', {}).get('ref', '')]
    with_rot = [g for g in gates if g.get('rot', 0) != 0]
    rot_vals = [g['rot'] for g in with_rot]
    print(f'  {ref}: {len(gates)} gates, {len(with_rot)} rotated {rot_vals}')
