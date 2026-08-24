import json

with open('docs/terminal_layout.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== Vertical thin rects (w < 20, h > 20) ===")
for s in data['all_shapes']:
    if s['w'] < 20 and s['h'] > 20 and s['w'] > 0:
        label = ''
        if s['name'] in [t['name'] for t in data['terminals']]:
            label = '[TERMINAL]'
        elif s['name'] in [p['name'] for p in data['piers']]:
            label = '[PIER]'
        elif s['name'] in [g['name'] for g in data['gates']]:
            label = '[GATE]'
        else:
            label = '[UNCLASSIFIED]'
        print(f"  {s['name']}: w={s['w']:.1f}, h={s['h']:.1f}, x={s['x']:.1f}, y={s['y']:.1f} {label}")

print("\n=== Rect gates (w<50, h<15) ===")
for g in data['gates']:
    if g['type'] == 'rect':
        print(f"  {g['name']}: w={g['w']:.1f}, h={g['h']:.1f}")

print("\n=== Arrow gates ===")
for g in data['gates']:
    if g['type'] in ('upArrow', 'downArrow'):
        print(f"  {g['name']}: w={g['w']:.1f}, h={g['h']:.1f} dir={g.get('gate_dir','?')}")

print("\n=== Piers ===")
for p in data['piers']:
    print(f"  {p['name']}: w={p['w']:.1f}, h={p['h']:.1f}, x={p['x']:.1f}, y={p['y']:.1f}")
