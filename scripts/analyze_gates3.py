import json

d = json.load(open('docs/terminal_layout.json', encoding='utf-8'))

# 按 pier 分组 rect gates
pier_groups = {}
for g in d['gates']:
    if g['type'] != 'rect':
        continue
    a = g.get('attach', {})
    ref = a.get('ref', '?')
    if ref not in pier_groups:
        pier_groups[ref] = []
    pier_groups[ref].append(g)

print("=== Rect gates per pier ===")
for ref, gates in sorted(pier_groups.items()):
    sides = {}
    for g in gates:
        s = g.get('attach', {}).get('side', '?')
        sides[s] = sides.get(s, 0) + 1
    print(f"  {ref}: total={len(gates)}, sides={sides}")

# Pier locations & sizes
print("\n=== Pier info ===")
for p in d['piers']:
    print(f"  {p['name']}: pos=({p['x']:.0f},{p['y']:.0f}), size=({p['w']:.0f}x{p['h']:.0f})")

# Which pier belongs to which terminal?
print("\n=== Spatial grouping ===")
t1 = d['terminals'][0]
t2 = d['terminals'][1]
t1_right = t1['x'] + t1['w']
t2_left = t2['x']
mid = (t1_right + t2_left) / 2
print(f"T1 right edge={t1_right:.0f}, T2 left edge={t2_left:.0f}, mid={mid:.0f}")

for p in d['piers']:
    pcx = p['x'] + p['w'] / 2
    terminal = 'T1' if pcx < mid else 'T2'
    print(f"  {p['name']} -> {terminal}  (center_x={pcx:.0f})")

# Also list terminals
for t in d['terminals']:
    print(f"  {t['terminal_name']}: center=({t['x']+t['w']/2:.0f},{t['y']+t['h']/2:.0f})")
