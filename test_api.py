import urllib.request, json
req = urllib.request.Request(
    'http://127.0.0.1:8747/query', 
    data=json.dumps({"query": "hello"}).encode('utf-8'), 
    headers={'Content-Type': 'application/json'}
)
print(urllib.request.urlopen(req).read().decode())
