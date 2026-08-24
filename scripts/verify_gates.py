import json
d = json.load(open('docs/terminal_layout.json', encoding='utf-8'))
arrows = [g for g in d['gates'] if g['type'] in ('upArrow', 'downArrow')]
t1 = [g for g in arrows if g['x'] < 300]
t2 = [g for g in arrows if g['x'] > 300]
print(f"T1: entry={sum(1 for g in t1 if g['gate_dir']=='entry')}, exit={sum(1 for g in t1 if g['gate_dir']=='exit')}")
print(f"T2: entry={sum(1 for g in t2 if g['gate_dir']=='entry')}, exit={sum(1 for g in t2 if g['gate_dir']=='exit')}")
for g in t1: print(f"  {g['name']}: dir={g['gate_dir']}, pos=({g['x']:.0f},{g['y']:.0f})")
for g in t2: print(f"  {g['name']}: dir={g['gate_dir']}, pos=({g['x']:.0f},{g['y']:.0f})")
