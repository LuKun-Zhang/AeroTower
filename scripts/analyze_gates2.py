import json

d = json.load(open('docs/terminal_layout.json', encoding='utf-8'))

print("=== Arrow gates attachment ===")
for g in d['gates']:
    if g['type'] in ('upArrow', 'downArrow'):
        a = g.get('attach', {})
        print(f"  {g['name']}: dir={g.get('gate_dir','?')}, ref={a.get('ref','?')}, side={a.get('side','?')}, pos=({g['x']:.0f},{g['y']:.0f})")

# Pier locations
print("\n=== Piers ===")
for p in d['piers']:
    print(f"  {p['name']}: pos=({p['x']:.0f},{p['y']:.0f}), size=({p['w']:.0f}x{p['h']:.0f})")

# Terminal locations
print("\n=== Terminals ===")
for t in d['terminals']:
    print(f"  {t['terminal_name']}: pos=({t['x']:.0f},{t['y']:.0f}), size=({t['w']:.0f}x{t['h']:.0f})")
