#!/usr/bin/env python3
import os
import json
import urllib.request
import feedparser
import anthropic
from datetime import datetime, timezone

RSS_FEEDS = [
    # International
    ("BBC Sport Rugby Union", "https://feeds.bbci.co.uk/sport/rugby-union/rss.xml"),
    ("BBC Sport Rugby League", "https://feeds.bbci.co.uk/sport/rugby-league/rss.xml"),
    ("Sky Sports Rugby", "https://www.skysports.com/rss/12040"),
    ("The Guardian Rugby", "https://www.theguardian.com/sport/rugby-union/rss"),
    ("RugbyPass", "https://www.rugbypass.com/feed/"),
    ("Planet Rugby", "https://www.planetrugby.com/feed/"),
    ("Rugby365", "https://en.rugby365.com/latest/feed/"),
    # South Africa
    ("SA Rugby Magazine", "https://sarugbymag.co.za/feed/"),
    ("Netwerk24 Sport", "https://www.netwerk24.com/feeds/sport/rugby"),
    ("The Citizen Rugby", "https://citizen.co.za/sport/rugby/feed/"),
    ("IOL Rugby", "https://www.iol.co.za/sport/rugby/rss"),
    # Ireland & UK
    ("Irish Express", "https://www.irishexpress.co.uk/feed/"),
    ("Wales Online Rugby", "https://www.walesonline.co.uk/sport/rugby/rss.xml"),
    ("NewsNow Rugby Union", "https://feeds.newsnow.co.uk/newsfeeds/sport/rugby-union.rss"),
    # New Zealand
    ("NZ Herald Rugby", "https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/sport/rugby/"),
    ("The Post NZ Rugby", "https://www.thepost.co.nz/sport/rugby/rss/"),
    ("Stuff NZ Rugby", "https://www.stuff.co.nz/sport/rugby/rss"),
    # Australia
    ("The Age Rugby", "https://www.theage.com.au/rss/sport/rugby-union.xml"),
]


def fetch_stories():
    stories = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if title and link:
                    stories.append({
                        "source": source,
                        "title": title,
                        "link": link,
                        "summary": summary[:300],
                    })
        except Exception as e:
            print(f"Warning: could not fetch {source}: {e}")
    return stories


def rank_and_format(stories):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")

    stories_text = "\n\n".join(
        f"[{i+1}] SOURCE: {s['source']}\nTITLE: {s['title']}\nURL: {s['link']}\nSUMMARY: {s['summary']}"
        for i, s in enumerate(stories)
    )

    prompt = f"""You are a senior rugby journalist. Today is {today}.

Rank these rugby stories by global importance and format them as a polished daily digest email.

Rules:
- Remove duplicates (keep the best-sourced version)
- Rank by importance: Test match results > Lions/World Cup news > Super Rugby/URC/Top 14 results > transfers > injuries > opinion
- Select the top 15-20 stories
- Group into categories (omit any with no stories):
  1. Test Rugby & International
  2. Super Rugby & Club Competitions
  3. Transfers & Contracts
  4. Injuries & Team News
  5. Analysis & Opinion
  6. Other

Output a complete HTML email body (no <html>/<head>/<body> tags — just the content div):
- Outer wrapper: <div style="font-family: Georgia, serif; max-width: 680px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
- Header: today's date + "Rugby Daily Digest" title in dark green (#1a4d2e), bold, 28px
- Each category: bold heading, border-bottom: 2px solid #e8e8e8, margin-top: 28px
- Each story: numbered, headline as hyperlink (color: #1a4d2e), source name in grey (font-size: 13px), then one sentence explaining why it matters (max 25 words, your own words)
- Footer in grey: "Delivered daily by Rugby Digest Agent"

Then output exactly: ---PLAINTEXT---
Followed by a plain-text version with the same stories and summaries.

STORIES:
{stories_text}"""

    msg = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    full = msg.content[0].text
    if "---PLAINTEXT---" in full:
        html, plain = full.split("---PLAINTEXT---", 1)
    else:
        html, plain = full, full
    return html.strip(), plain.strip()


def send_email(html_body, plain_body):
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    payload = json.dumps({
        "from": "Rugby Digest <onboarding@resend.dev>",
        "to": ["brendennel@gmail.com"],
        "subject": f"Rugby Daily Digest — {today}",
        "html": html_body,
        "text": plain_body,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
                headers={
            "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type": "application/json",
            "User-Agent": "rugby-digest/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            print(f"Email sent successfully: {result}")
    except urllib.error.HTTPError as e:
        print(f"Resend API error {e.code}: {e.read().decode()}")
        raise


def main():
    print("Fetching rugby stories...")
    stories = fetch_stories()
    print(f"Fetched {len(stories)} stories from {len(RSS_FEEDS)} feeds.")

    if not stories:
        print("No stories found — aborting.")
        return

    print("Ranking and formatting with Claude...")
    html_body, plain_body = rank_and_format(stories)

    print("Sending email via Resend...")
    send_email(html_body, plain_body)
    print("Done.")


if __name__ == "__main__":
    main()