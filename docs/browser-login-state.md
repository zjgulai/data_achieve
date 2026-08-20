# Browser Login State Management

## Overview

This document describes how to configure persistent browser login states for platforms that require authentication (Instagram, LinkedIn, etc.).

## Architecture

The platform uses Playwright's `user_data_dir` feature to persist browser context (cookies, localStorage, sessionStorage) across collection runs.

```
/app/browser_data/
├── instagram/          # Instagram login state
├── linkedin/           # LinkedIn login state
├── facebook/           # Facebook login state
└── xiaohongshu/        # 小红书 login state
```

## Configuration

### 1. Docker Volume Mount

Add browser data persistence to `docker-compose.yml`:

```yaml
services:
  api:
    volumes:
      - scrapy_export_data:/app/exports
      - browser_data:/app/browser_data  # Add this line

volumes:
  browser_data:
    name: data_achieve_scrapy_browser_data
```

### 2. Manual Login (One-time Setup)

For each platform requiring authentication:

1. Start a Playwright browser with persistent context:

```bash
# Enter API container
docker exec -it data_achieve_scrapy_api bash

# Launch browser for Instagram login
uv run python -c "
import asyncio
from playwright.async_api import async_playwright

async def setup_instagram():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir='/app/browser_data/instagram',
            headless=False,
            args=['--no-sandbox']
        )
        page = await browser.new_page()
        await page.goto('https://www.instagram.com/accounts/login/')
        input('Login manually, then press Enter to save and exit...')
        await browser.close()

asyncio.run(setup_instagram())
"
```

2. Log in manually in the opened browser
3. Press Enter to save the session
4. Future collector runs will reuse this login state

### 3. Supported Platforms

| Platform | Collector Type | Context Dir |
|----------|----------------|-------------|
| Instagram | `mediacrawler_instagram_*` | `/app/browser_data/instagram` |
| LinkedIn | `mediacrawler_linkedin_*` | `/app/browser_data/linkedin` |
| Facebook | `apify_facebook_*` | `/app/browser_data/facebook` |
| 小红书 | `mediacrawler_xiaohongshou_*` | `/app/browser_data/xiaohongshu` |

## MediaCrawler Integration

The MediaCrawler collector already supports persistent context via the `user_data_dir` configuration parameter.

Example collector config:

```json
{
  "collector_type": "mediacrawler_instagram_user_posts",
  "config": {
    "username": "target_user",
    "max_posts": 50,
    "use_persistent_context": true
  }
}
```

When `use_persistent_context` is enabled, the collector automatically loads the saved login state from `/app/browser_data/{platform}`.

## Troubleshooting

### Session Expired

If collectors fail with authentication errors:

1. Re-run the manual login script to refresh the session
2. Check if the platform requires 2FA (currently not automated)

### Context Lock

If you see "browser context is locked" errors:

```bash
# Remove lock files
docker exec data_achieve_scrapy_api rm -f /app/browser_data/*/SingletonLock
```

## Security Notes

- Browser data volumes contain sensitive authentication tokens
- Ensure proper access controls on production volumes
- Do not expose `/app/browser_data` via API endpoints
- Rotate sessions periodically (e.g., every 30 days)

## Future Enhancements (P1)

- [ ] Automatic login script with credentials from env vars
- [ ] 2FA code handling via IMAP/SMS gateway
- [ ] Session health check and auto-refresh
- [ ] Multi-account rotation per platform
