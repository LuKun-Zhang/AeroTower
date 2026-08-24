import json

d = json.load(open('docs/terminal_layout.json', encoding='utf-8'))

# 分组：按归属 terminal name
t1_entry = []
t1_exit = []
t2_entry = []
t2_exit = []

for g in d['gates']:
    a = g.get('attach', {})
    ref = a.get('ref', '')
    side = a.get('side', '')
    is_arrow = g['type'] in ('upArrow', 'downArrow')
    gate_dir = g.get('gate_dir', '')
    name = g['name']
    
    if '航站楼1' in ref:
        if is_arrow:
            if gate_dir == 'entry':
                t1_entry.append(f"  {name}: side={side}, pos=({g['x']:.0f},{g['y']:.0f})")
            else:
                t1_exit.append(f"  {name}: side={side}, pos=({g['x']:.0f},{g['y']:.0f})")
    elif '航站楼2' in ref:
        if is_arrow:
            if gate_dir == 'entry':
                t2_entry.append(f"  {name}: side={side}, pos=({g['x']:.0f},{g['y']:.0f})")
            else:
                t2_exit.append(f"  {name}: side={side}, pos=({g['x']:.0f},{g['y']:.0f})")

print("=== T1 入口 ===")
for e in t1_entry: print(e)
print(f"  count={len(t1_entry)}")

print("\n=== T1 出口 ===")
for e in t1_exit: print(e)
print(f"  count={len(t1_exit)}")

print("\n=== T2 入口 ===")
for e in t2_entry: print(e)
print(f"  count={len(t2_entry)}")

print("\n=== T2 出口 ===")
for e in t2_exit: print(e)
print(f"  count={len(t2_exit)}")

# Also count rect gates attached to terminals
print("\n=== Rect gates on terminals ===")
for g in d['gates']:
    if g['type'] == 'rect':
        a = g.get('attach', {})
        ref = a.get('ref', '')
        if ref and '航站楼' in ref:
            print(f"  {g['name']}: ref={ref}, side={a.get('side','?')}, pos=({g['x']:.0f},{g['y']:.0f}), rot={g.get('rot',0)}")

# Check rect gates on piers
print("\n=== Rect gates on piers (sample) ===")
pier_gates = [g for g in d['gates'] if g['type'] == 'rect' and g.get('attach', {}).get('ref', '') not in ('航站楼1', '航站楼2')]
pier_names = set(g.get('attach', {}).get('ref', '') for g in pier_gates)
print(f"Pier refs: {pier_names}")
print(f"Total pier gates: {len(pier_gates)}")
