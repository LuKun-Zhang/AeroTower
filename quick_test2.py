import urllib.request, json

data = json.dumps({'airport': '成都', 'mode': 'chain'}).encode()
req = urllib.request.Request('http://127.0.0.1:5000/api/schedule/crew', data=data, headers={'Content-Type': 'application/json'}, method='POST')
try:
    resp = json.loads(urllib.request.urlopen(req).read())
    print(f"code={resp.get('code')}, msg={resp.get('msg', 'N/A')}")
except Exception as e:
    print(f"HTTP Error: {e}")
    import traceback
    traceback.print_exc()
