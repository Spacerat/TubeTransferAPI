curl -H "Accept: application/json" http://127.0.0.1:8000/containers/ | python -m json.tool
curl -X POST -H "Accept: application/json" -H "Content-Type: application/json" -d '{"into":1}' http://127.0.0.1:8000/containers/2/transfer/ | python -m json.tool

