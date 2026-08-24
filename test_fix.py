import urllib.request, json

# Direct test
r = urllib.request.urlopen("http://127.0.0.1:5000/api/crew/substitutions")
d = json.loads(r.read())
print("Before:", d["data"]["count"], "substitutions")

req = urllib.request.Request("http://127.0.0.1:5000/api/schedule/crew",
    data=json.dumps({"airport":"成都","mode":"chain"}).encode(),
    headers={"Content-Type":"application/json"}, method="POST")
r = urllib.request.urlopen(req)
d = json.loads(r.read())
print("Chengdu crew:", len(d["data"].get("crew",[])))

r = urllib.request.urlopen("http://127.0.0.1:5000/api/crew/substitutions")
d = json.loads(r.read())
print("After:", d["data"]["count"], "substitutions")
