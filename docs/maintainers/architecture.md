# Architecture and adding games

```text
Prydwen facade
  games/<game>/client.py
    core/client.py -> core/cache.py
                   -> core/transport.py
    games/<game>/parsers/* -> parsing/*
    games/<game>/models/*
```

Game clients choose a resource, model, and pure parser. The shared loader manages context lifecycle, coalescing, cache validation, fetches, parsing workers, and atomic persistence. Parsers perform no I/O. Models do not fetch relationships or images.

The site uses streaming SSR, including primary DOM content inside hidden containers. Select known section roots without discarding hidden content. The embedded adapter decodes a bounded subset of literal Next.js JSON text frames; it never evaluates JavaScript or treats unstable Flight IDs/array positions as selectors. Missing optional embedded enrichment falls back to DOM with diagnostics; missing required identities raises an error.

## Add another game

1. Create `src/prydwen/games/<game>/` with endpoints, client, models, and parsers.
2. Supply the known resource set and game key to the shared base client.
3. Add pure parsers and fixture-based tests for that game's HTML shape.
4. Import and alias its client on the root `Prydwen` facade.
5. Register its known resource keys with root cache clearing and document the new API.

Keep source keys, display names, official game IDs, and local fallback identifiers distinct. New games can use different domain models while sharing only transport/cache/provenance primitives. Do not add game-specific selectors to the shared loader.

The original research design is in `plan.md`. Runtime models use lists for the user's collection contract and collection metadata directly on each dataset. There is no separate envelope object in the public return API.
