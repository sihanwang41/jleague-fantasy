# Start server
```shell
uvicorn main:app --host 0.0.0.0 --port $PORT
```

# Get players score
```shell
curl -X 'GET' \
  'http://127.0.0.1:8000/score' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "players": ["J34531", "J45270"]
}'
```
