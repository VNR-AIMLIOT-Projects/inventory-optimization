from starlette.datastructures import Headers
h = Headers({"x-api-key": "secret"})
print("x-api-key:", h.get("x-api-key"))
print("X-API-Key:", h.get("X-API-Key"))
