curl -v -X POST http://127.0.0.1:8000/api/upload \
  -H "Content-Type: application/json" \
  -H "api-key: something-stupid-over-here" \
  -d @packet.json