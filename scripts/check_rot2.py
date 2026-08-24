import json
d = json.load(open('docs/terminal_layout.json', encoding='utf-8'))
cnt = [g for g in d['gates'] if g.get('rot', 0) != 0]
print(f'Gates with rotation: {len(cnt)}')
for g in cnt[:15]:
    print(f"  {g['name']}: rot={g['rot']}, type={g['type']}")
