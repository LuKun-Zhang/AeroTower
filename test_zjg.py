import urllib.request, json

# 测试两种模式
for mode in ("greedy", "pairing"):
    print(f"\n{'='*40}\n模式: {mode}\n{'='*40}")
    data = json.dumps({"airport": "成都", "mode": mode}).encode()
    req = urllib.request.Request("http://127.0.0.1:5000/api/schedule/crew",
                                  data=data, headers={"Content-Type": "application/json"}, method="POST")
    resp = json.loads(urllib.request.urlopen(req).read())
    crew = resp["data"]["crew"]

    overlap = 0
    for c in crew:
        if "张建国" not in c["name"]:
            continue
        # 按日期排序
        flights = sorted(c["assigned_flights"], key=lambda a: (a["date"], a["duty_start_min"]))
        print(f"\n{c['name']}:")
        for a in flights:
            print(f"  {a['date']} {a['flight_no']} {a['duty_start_min']//60:02d}:{a['duty_start_min']%60:02d}-{a['duty_end_min']//60:02d}:{a['duty_end_min']%60:02d}")
        for i in range(len(flights)):
            for j in range(i+1, len(flights)):
                if flights[i]["date"] == flights[j]["date"]:
                    if flights[i]["duty_end_min"] > flights[j]["duty_start_min"]:
                        overlap += 1
                        print(f"  !!OVERLAP: {flights[i]['flight_no']} end={flights[i]['duty_end_min']} vs {flights[j]['flight_no']} start={flights[j]['duty_start_min']}")

    print(f"\n张建国重叠={overlap}, 报告={resp['data']['report'].get('summary','')}")
