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

response
```shell
{"players_score":[["菅野 孝憲",14],["阿波加 俊太",0]],"total_scores":14}
```