"""Renders a digest's HTML body into a full static page under docs/, for GitHub Pages."""

import os
from datetime import datetime, timezone

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="manifest" href="manifest.json">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<meta name="theme-color" content="#1a4d2e">
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; padding:0 0 48px; background:#f7f5f0; }}
  .nav {{
    display:flex; gap:8px; padding:14px 16px; max-width:680px; margin:0 auto;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  .nav a {{
    padding:6px 16px; border-radius:16px; background:#e8e8e8; color:#333;
    text-decoration:none; font-size:14px; font-weight:600;
  }}
  .nav a.active {{ background:#1a4d2e; color:#fff; }}
  .updated {{
    max-width:680px; margin:0 auto 8px; padding:0 16px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size:12px; color:#888;
  }}
</style>
</head>
<body>
<div class="nav">
  <a href="daily.html" class="{daily_active}">Daily Digest</a>
  <a href="teams.html" class="{teams_active}">Team News</a>
</div>
<div class="updated">Updated {updated}</div>
{body}
</body>
</html>
"""


def write_page(html_body: str, page: str) -> None:
    """page is 'daily' or 'teams'."""
    os.makedirs("docs", exist_ok=True)
    title = "Rugby Daily Digest" if page == "daily" else "Rugby Team News"
    updated = datetime.now(timezone.utc).strftime("%a %d %b %Y, %H:%M UTC")
    out = PAGE_TEMPLATE.format(
        title=title,
        body=html_body,
        daily_active="active" if page == "daily" else "",
        teams_active="active" if page == "teams" else "",
        updated=updated,
    )
    with open(f"docs/{page}.html", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote docs/{page}.html")
