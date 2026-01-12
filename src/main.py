"""Plex Intro Detector - Entry point and orchestration."""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


def parse_interval(value: str) -> int | None:
    """Parse interval string like '6h', '30m', '1d' to seconds. Returns None if not set."""
    if not value:
        return None
    match = re.match(r"^(\d+)([smhd])$", value.lower())
    if not match:
        log.warning(f"Invalid RUN_INTERVAL format: {value}. Use format like '6h', '30m', '1d'")
        return None
    num, unit = int(match.group(1)), match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return num * multipliers[unit]


def load_config() -> dict:
    """Load configuration from environment variables."""
    required = ["PLEX_URL", "PLEX_TOKEN", "TAUTULLI_URL", "TAUTULLI_API_KEY", "TARGET_USERS"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        log.error(f"Missing required env vars: {', '.join(missing)}")
        sys.exit(1)

    return {
        "plex_url": os.environ["PLEX_URL"],
        "plex_token": os.environ["PLEX_TOKEN"],
        "tautulli_url": os.environ["TAUTULLI_URL"],
        "tautulli_api_key": os.environ["TAUTULLI_API_KEY"],
        "target_users": [u.strip() for u in os.environ["TARGET_USERS"].split(",")],
        "lookback_days": int(os.getenv("LOOKBACK_DAYS", "7")),
        "dry_run": os.getenv("DRY_RUN", "false").lower() == "true",
        "state_file": Path(os.getenv("STATE_FILE", "/config/analyzed.json")),
        "max_analyze": int(os.getenv("MAX_ANALYZE", "20")),
        "run_interval": parse_interval(os.getenv("RUN_INTERVAL", "")),
        "skip_watched": os.getenv("SKIP_WATCHED", "true").lower() == "true",
    }


def load_state(path: Path) -> set[int]:
    """Load analyzed rating keys from JSON file."""
    if path.exists():
        try:
            return set(json.loads(path.read_text()))
        except (json.JSONDecodeError, TypeError):
            return set()
    return set()


def save_state(path: Path, analyzed: set[int]) -> None:
    """Save analyzed rating keys to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(analyzed)))


def run_once(config: dict) -> None:
    """Run one detection cycle."""
    log.info(f"Starting intro detection for users: {', '.join(config['target_users'])}")

    # Connect to services (fail fast)
    try:
        from .clients import TautulliClient, PlexClient
        tautulli = TautulliClient(config["tautulli_url"], config["tautulli_api_key"])
        plex = PlexClient(config["plex_url"], config["plex_token"])
    except Exception as e:
        log.error(f"Failed to connect: {e}")
        sys.exit(1)

    # Load state
    analyzed = load_state(config["state_file"])

    # Get shows and episodes watched by target users
    try:
        watched_shows, watched_episodes = tautulli.get_watched_shows(config["target_users"], config["lookback_days"])
    except Exception as e:
        log.error(f"Failed to get watch history: {e}")
        sys.exit(1)

    log.info(f"Found {len(watched_shows)} shows watched by target users ({len(watched_episodes)} episodes)")

    # Process all episodes from watched shows
    stats = {"skipped_analyzed": 0, "skipped_has_marker": 0, "skipped_already_scanned": 0, "skipped_watched": 0, "analyzed": 0, "failed": 0, "shows": 0}
    max_analyze = config["max_analyze"]

    for show_key in watched_shows:
        show = plex.get_show(show_key)
        if not show:
            log.warning(f"Show {show_key} not found")
            continue

        stats["shows"] += 1
        episodes = plex.get_all_episodes(show)
        log.info(f"Processing {show.title}: {len(episodes)} episodes")

        for episode in episodes:
            # Stop if we've hit the limit
            if stats["analyzed"] >= max_analyze:
                log.info(f"Reached max analyze limit ({max_analyze}), stopping")
                break

            rating_key = episode.ratingKey

            if rating_key in analyzed:
                stats["skipped_analyzed"] += 1
                continue

            if plex.has_intro_marker(episode):
                stats["skipped_has_marker"] += 1
                analyzed.add(rating_key)
                continue

            if plex.has_credits_marker(episode):
                stats["skipped_already_scanned"] += 1
                analyzed.add(rating_key)
                continue

            if config["skip_watched"] and rating_key in watched_episodes:
                stats["skipped_watched"] += 1
                analyzed.add(rating_key)
                continue

            if config["dry_run"]:
                log.info(f"[DRY RUN] Would analyze: {show.title} - {episode.title}")
            else:
                try:
                    plex.analyze(episode)
                except Exception as e:
                    log.error(f"Failed to analyze {rating_key}: {e}")
                    stats["failed"] += 1
                    continue

            analyzed.add(rating_key)
            stats["analyzed"] += 1

        # Break outer loop too if limit reached
        if stats["analyzed"] >= max_analyze:
            break

    # Save state (skip in dry run mode)
    if not config["dry_run"]:
        save_state(config["state_file"], analyzed)

    # Summary
    log.info(
        f"Complete: {stats['shows']} shows, {stats['analyzed']} analyzed, "
        f"{stats['skipped_analyzed']} skipped (already processed), "
        f"{stats['skipped_has_marker']} skipped (has intro), "
        f"{stats['skipped_already_scanned']} skipped (already scanned), "
        f"{stats['skipped_watched']} skipped (already watched), "
        f"{stats['failed']} failed"
    )


def main():
    """Main entry point with optional scheduler."""
    config = load_config()
    interval = config["run_interval"]

    if interval:
        log.info(f"Scheduler enabled: running every {interval}s")
        while True:
            try:
                run_once(config)
            except Exception as e:
                log.error(f"Run failed: {e}")
            log.info(f"Sleeping for {interval}s...")
            time.sleep(interval)
    else:
        run_once(config)


if __name__ == "__main__":
    main()
