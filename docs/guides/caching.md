# Caching and refresh

The default root is captured when you construct a client: **`Path.cwd() / ".prywen_cache"`**. Its exact spelling is intentional. Endfield stores one JSON file per section under `arknights-endfield/` plus derived discovery metadata.

```text
.prywen_cache/
  arknights-endfield/
    characters.json
    weapons.json
    gear.json
    banners.json
    codes.json
    tier_list.json
    team_tier_list.json
    metadata.json
```

Valid entries have no automatic TTL. They remain until you refresh or clear them. A missing, corrupt, incompatible, or checksum-mismatched entry triggers a request and parsing for that one endpoint.

`force_new=True` bypasses cached data and writes a replacement only after parsing and validation succeed. A failed refresh raises a typed exception and preserves the old file. It never silently returns old data as a successful forced refresh.

Cache writes use a temporary file in the same directory followed by atomic replacement. Calls within one client coalesce simultaneous requests for the same resource. Separate processes can each fetch; the last valid writer wins. Returned models are reconstructed from disk, so changing a returned list does not change future cached results.

The cache stores no cookies, HTTP sessions, challenge pages, or Python pickles. Metadata records discovered identities and actual character paths; it can be rebuilt from valid catalogs without network access.

## Override or clear

```python
from pathlib import Path
from prydwen import Prydwen

cache_root = Path("data/prydwen-cache")

async with Prydwen.Endfield(cache_dir=cache_root) as endfield:
    await endfield.characters()

await Prydwen.clear_cache("arknights-endfield", resource="characters", cache_dir=cache_root)
await Prydwen.clear_cache("arknights-endfield", cache_dir=cache_root)
await Prydwen.clear_cache(cache_dir=cache_root)
```

Pass the same root override when clearing. Resource keys are `characters`, `weapons`, `gear`, `banners`, `codes`, `tier_list`, and `team_tier_list`. Gear and gear sets share `gear`. Clearing invalidates in-process writers that started before the clear. Another process can later repopulate a cleared resource.

Cache targets must stay inside the configured root; linked paths are rejected. If the working directory changes, an existing client keeps the root it captured. A separate `clear_cache()` call captures its own default CWD, so pass the original root explicitly when needed.
