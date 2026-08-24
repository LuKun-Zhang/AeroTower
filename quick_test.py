import urllib.request, json

data = json.dumps({'airport': '成都', 'mode': 'chain'}).encode()
req = urllib.request.Request('http://127.0.0.1:5000/api/schedule/crew', data=data, headers={'Content-Type': 'application/json'}, method='POST')
resp = json.loads(urllib.request.urlopen(req).read())
crew_data = resp.get('data', {})

crew_list = crew_data.get('crew', [])
print(f"Total crew: {len(crew_list)}, Mode: {crew_data.get('mode')}")
for c in crew_list:
    name = c.get('name', '?')
    role = c.get('role', '?')
    tid = c.get('team_id', '?')
    flights = len(c.get('assigned_flights', []))
    print(f"  {name} ({role}): team_id={tid}, flights={flights}")

teams = crew_data.get('team_groups', [])
print(f"\nTeam groups: {len(teams)}")
for t in teams:
    members = ' / '.join([t.get('captain',''), t.get('officer',''), t.get('purser',''), *t.get('attendants',[])])
    is_sub = t.get('is_substitute', False)
    tag = ' [SUB]' if is_sub else ''
    print(f'  team_id={t["team_id"]}: {members} ({t["shared_flights"]}班){tag}')
