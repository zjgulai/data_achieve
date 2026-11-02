#!/usr/bin/env python3
"""Seed meta.actor_registry and backfill raw.apify_dataset attribution.

The first T-1 scan produced 131 datasets with ``platform=other`` and
``object_type=unknown`` because the registry was empty. This script maps the
nine actors seen in that scan to a platform and object type.

The mapping is keyed by actor name, not act_id, so it is stable when Apify
rotates act_ids. Six of the nine actors are not in
``scripts/apify_lake/actor_map.json`` (they are not in the endpoint catalog),
so a generated map would leave them unattributed. Manual rows use
``source='manual'`` and ``confidence='medium'``; the catalog-backed row uses
``source='catalog'`` and ``confidence='high'``.

Copy the script and ``actid_map.json`` into the API container, then run:

    python /tmp/seed_abi_actor_registry.py --dry-run
    python /tmp/seed_abi_actor_registry.py --execute
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from data_intelligence_hub.core.database import async_session_factory

# actor_name -> (platform, object_type, endpoint_type, source, confidence)
BY_NAME: dict[str, tuple[str, str, str | None, str, str]] = {
    "clockworks/free-tiktok-scraper": ("tiktok", "post", None, "manual", "medium"),
    "streamers/youtube-scraper": ("youtube", "post", None, "manual", "medium"),
    "clockworks/tiktok-hashtag-scraper": ("tiktok", "hashtag", None, "manual", "medium"),
    "scraper_one/x-posts-search": ("x", "post", None, "manual", "medium"),
    "apify/instagram-hashtag-scraper": (
        "instagram",
        "post",
        "apify_instagram_hashtag_scraper",
        "catalog",
        "high",
    ),
    "apidojo/tweet-scraper": ("x", "post", None, "manual", "medium"),
    "apify/instagram-tagged-scraper": ("instagram", "post", None, "manual", "medium"),
    "clearpath/reddit-subreddit-posts-scraper": ("reddit", "post", None, "manual", "medium"),
    "trudax/reddit-scraper-lite": ("reddit", "post", None, "manual", "medium"),
}


def load_actors(path: Path) -> dict[str, tuple[str, str, str, str | None, str, str]]:
    """Return act_id -> (actor_name, platform, object_type, endpoint_type, source, confidence)."""
    actid_map = json.loads(path.read_text(encoding="utf-8"))
    selected: dict[str, tuple[str, str, str, str | None, str, str]] = {}
    for act_id, actor_name in actid_map.items():
        mapping = BY_NAME.get(actor_name)
        if mapping is not None:
            platform, object_type, endpoint_type, source, confidence = mapping
            selected[act_id] = (
                actor_name,
                platform,
                object_type,
                endpoint_type,
                source,
                confidence,
            )
    return selected


async def seed(
    actors: dict[str, tuple[str, str, str, str | None, str, str]], *, execute: bool
) -> None:
    async with async_session_factory() as session:
        for act_id, row in actors.items():
            actor_name, platform, object_type, endpoint_type, source, confidence = row
            if execute:
                await session.execute(
                    text(
                        """
                        INSERT INTO meta.actor_registry
                            (id, actor_id, actor_name, platform, object_type,
                             endpoint_type, source, confidence, deprecated)
                        VALUES
                            (gen_random_uuid(), :actor_id, :actor_name, :platform,
                             :object_type, :endpoint_type, :source, :confidence, false)
                        ON CONFLICT (actor_id) DO UPDATE
                        SET actor_name = EXCLUDED.actor_name,
                            platform = EXCLUDED.platform,
                            object_type = EXCLUDED.object_type,
                            endpoint_type = EXCLUDED.endpoint_type,
                            source = EXCLUDED.source,
                            confidence = EXCLUDED.confidence
                        """
                    ),
                    {
                        "actor_id": act_id,
                        "actor_name": actor_name,
                        "platform": platform,
                        "object_type": object_type,
                        "endpoint_type": endpoint_type,
                        "source": source,
                        "confidence": confidence,
                    },
                )
        if execute:
            result = await session.execute(
                text(
                    """
                    UPDATE raw.apify_dataset AS d
                    SET platform = r.platform,
                        object_type = r.object_type,
                        endpoint_type = r.endpoint_type,
                        endpoint_source = r.source,
                        confidence = r.confidence
                    FROM meta.actor_registry AS r
                    WHERE d.act_id = r.actor_id
                      AND d.endpoint_source = 'unknown'
                    RETURNING d.dataset_id
                    """
                )
            )
            updated = len(result.all())
            await session.commit()
            print({"actors": len(actors), "datasets_updated": updated, "execute": True})
        else:
            print({"actors": len(actors), "execute": False})
            print("dry-run: no rows written")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--actid-map",
        default=str(Path(__file__).with_name("actid_map.json")),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    actors = load_actors(Path(args.actid_map))
    if not actors:
        raise SystemExit("no matching actors in actid map")
    if args.dry_run or not args.execute:
        print({"actors": len(actors), "execute": False})
        for act_id, row in actors.items():
            print(f"  {act_id} -> {row[0]} ({row[1]}/{row[2]})")
        return 0
    asyncio.run(seed(actors, execute=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
