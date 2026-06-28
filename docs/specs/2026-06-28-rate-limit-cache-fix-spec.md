# Project DevLog: inventory-optimization
* **📅 Date**: 2026-06-28
* **🏷️ Tags**: `#BugFix` `#DevLog` `#Caching` `#Spec`

---

> 🎯 **Progress Summary**
> Resolved a critical cache miss bug in the FastAPI backend related to dependency injection and `fastapi-cache2`. Implemented custom cache key builders and dedicated caching logs.

### 🛠️ Execution Details & Changes
* **Git Commits**:
  * `feat(cache,api): add LoggingRedisBackend to log cache hits/misses and increase rate limit`
  * `fix(cache): fix custom_key_builder to correctly intercept kwargs passed by fastapi-cache to prevent cache misses on endpoints with dependencies`
  * `chore: untrack agent context and .agents files`
* **Core File Modifications**:
  * `Backend-RL/src/main.py`
  * `Backend-RL/src/api/routers/legacy_routes.py` (fixed SKU season in evaluation)

* **Technical Implementation (Specification)**:
  * **Goal**: Ensure cached endpoints properly serve from Redis to reduce API latency.
  * **Logging**: Introduced a custom `LoggingRedisBackend` class that inherits from `RedisBackend`. It overrides `get_with_ttl` to explicitly log `[CACHE HIT]` and `[CACHE MISS]` to the terminal/docker logs, improving observability.
  * **Key Builder Override**: Overrode `FastAPICache.init()` with a `custom_key_builder`. The default key builder was capturing the SQLAlchemy `Session` object (`db: Session = Depends(get_db)`). Since `Session` generates a unique memory reference per request, `fastapi-cache` was treating identical requests as unique, leading to 100% cache misses.
  * **Solution**: The custom key builder iterates through the kwargs passed to the route, explicitly ignoring any dictionary key named `"db"` and any value of type `sqlalchemy.orm.Session`.

### 🚨 Troubleshooting
> 🐛 **Problem Encountered**: The cache was always missing (`[CACHE MISS]`) despite identical requests.
> 💡 **Solution**: Identified that `fastapi-cache` wraps the function kwargs into a single `"kwargs"` dictionary during interception. Fixed the `custom_key_builder` to extract `kwargs.get("kwargs", {})`, sanitize the `Session` dependency, and successfully achieve `[CACHE HIT]`.

### ⏭️ Next Steps
- [x] Create PR to `dev`.
- [ ] Review and merge PR #107.
- [ ] Test cached API endpoints (`/api/uploads`, `/api/demand/data`) locally on `dev`.
