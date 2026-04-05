import urllib.request, json
data = urllib.request.urlopen("http://localhost:8000/openapi.json").read()
d = json.loads(data)
for p in sorted(d.get("paths", {}).keys()):
    methods = list(d["paths"][p].keys())
    print(f"  {', '.join(m.upper() for m in methods):10s} {p}")
