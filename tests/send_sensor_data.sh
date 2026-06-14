curl -v -X POST http://127.0.0.1:8000/api/data \
  -H "Content-Type: application/json" \
  -H "x-api-key: something-stupid-over-here" \
  -d @packet.json