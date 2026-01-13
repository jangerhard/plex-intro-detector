# Plex Intro Detector

[![Docker Hub](https://img.shields.io/docker/v/jangerhard/plex-intro-detector?label=Docker%20Hub&logo=docker)](https://hub.docker.com/r/jangerhard/plex-intro-detector)
[![AI Generated](https://img.shields.io/badge/AI%20Generated-Claude-blueviolet)](https://claude.ai)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Disclaimer:** This project was generated with AI assistance (Claude). Review the code before deploying to your environment.

**A selective alternative to Plex's global intro detection - only analyze shows that matter.**

## Why?

Plex's built-in intro detection scans your **entire library**. For server owners, this means:

- Hours of CPU time spent analyzing shows only your friends watch
- Wasted resources on content that won't benefit from "Skip Intro" (non-Plex Pass users can't see the button anyway)

This tool lets you disable Plex's global scanning and only analyze shows that matter. Set `TARGET_USERS` to yourself, or include friends who have their own Plex Pass - anyone who can actually benefit from "Skip Intro".

**Bonus:** When you start a new show, this tool analyzes the entire series - so future episodes have "Skip Intro" ready before you get to them.

## Requirements

- **Plex Media Server** with Plex Pass
- **[Tautulli](https://tautulli.com/)** for watch history tracking
- **Docker**

### Plex Pass Note

"Skip Intro" requires Plex Pass for the viewing user:

- **Managed Users (Plex Home)** - Inherit the server owner's Plex Pass ✓
- **External users** - Need their own Plex Pass subscription

Without Plex Pass, intro markers exist but the skip button won't appear.

## How It Works

```mermaid
flowchart LR
    T[Tautulli] -->|watch history| P[plex-intro-detector]
    P -->|analyze| X[Plex]
    P -->|save state| S[(analyzed.json)]
```

1. Queries Tautulli for shows watched by target users
2. Gets all episodes from those shows (so future episodes are ready)
3. Skips episodes already processed or with existing markers
4. Triggers Plex's `analyze()` on remaining episodes
5. Saves state to avoid re-processing

### Smart Skip Logic

Episodes are skipped when:

- **Has intro marker** - Already has "Skip Intro"
- **Has credits marker** - Already scanned, no intro found
- **Already watched by target users** - No need for "Skip Intro" on seen content
- **In state file** - Previously processed

## Installation

### Option A: Docker Run

```bash
docker run -d \
  --name plex-intro-detector \
  -e PLEX_URL=http://your-plex:32400 \
  -e PLEX_TOKEN=your-plex-token \
  -e TAUTULLI_URL=http://your-tautulli:8181 \
  -e TAUTULLI_API_KEY=your-api-key \
  -e TARGET_USERS=alice,bob \
  -e RUN_INTERVAL=6h \
  -v ./config:/config \
  jangerhard/plex-intro-detector
```

### Option B: Docker Compose

```yaml
services:
  plex-intro-detector:
    image: jangerhard/plex-intro-detector
    container_name: plex-intro-detector
    environment:
      - PLEX_URL=http://your-plex:32400
      - PLEX_TOKEN=your-plex-token
      - TAUTULLI_URL=http://your-tautulli:8181
      - TAUTULLI_API_KEY=your-api-key
      - TARGET_USERS=alice,bob
      - RUN_INTERVAL=6h
    volumes:
      - ./config:/config
    restart: unless-stopped
```

```bash
docker compose up -d
```

### Test with Dry Run

Add `-e DRY_RUN=true` to see what would be analyzed without triggering Plex:

```
Found 5 shows watched by target users (42 episodes)
[DRY RUN] Would analyze: Show Name - Episode Title
Complete: 1 shows, 10 analyzed, 0 skipped...
```

## Configuration

### Required

| Variable | Description |
|----------|-------------|
| `PLEX_URL` | Plex server URL (e.g., `http://plex:32400`) |
| `PLEX_TOKEN` | Your Plex X-Plex-Token ([how to find](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)) |
| `TAUTULLI_URL` | Tautulli URL (e.g., `http://tautulli:8181`) |
| `TAUTULLI_API_KEY` | Tautulli API key (Settings → Web Interface) |
| `TARGET_USERS` | Comma-separated Plex usernames to monitor |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `LOOKBACK_DAYS` | `7` | Days of watch history to check |
| `DRY_RUN` | `false` | Log actions without executing |
| `MAX_ANALYZE` | `20` | Max episodes to analyze per run |
| `RUN_INTERVAL` | unset | Schedule interval (`6h`, `30m`, `1d`). If unset, runs once and exits |
| `SKIP_WATCHED` | `true` | Skip episodes already watched by target users |
| `STATE_FILE` | `/config/analyzed.json` | Path to state file |

## Initial Setup

For a new setup with existing watch history:

1. Set `LOOKBACK_DAYS=90` to catch all recently watched shows
2. Set `MAX_ANALYZE=50` to process larger batches
3. Run every 1-2 hours until caught up
4. Then reduce to `LOOKBACK_DAYS=7` for ongoing use

## Disabling Plex's Global Detection (Optional)

Once running, you can disable Plex's resource-heavy global scanning:

1. Plex → Settings → Library
2. Disable "Detect intros and credits"

This tool will handle intro detection for shows you actually watch.

## Troubleshooting

- **"Show not found" warnings** - Show may have been removed from Plex
- **Container can't reach Plex/Tautulli** - If all services are in the same Docker Compose stack, use container names (e.g., `http://plex:32400`). Otherwise, use LAN IP addresses. On macOS Docker Desktop, use `host.docker.internal`
- **No episodes found** - Check `TARGET_USERS` matches Tautulli usernames exactly (case-insensitive)
- **All episodes skipped** - Normal if already processed. Delete `config/analyzed.json` to reprocess

## License

[MIT](LICENSE)
