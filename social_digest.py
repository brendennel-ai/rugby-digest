#!/usr/bin/env python3
"""Rugby Social Digest — pulls official team RSS + YouTube feeds, ranks with Claude, emails via Gmail."""

import os
import json
import smtplib
import ssl
import feedparser
import anthropic
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------------------------------------------------------------
# TEAM WEBSITE RSS FEEDS
# ---------------------------------------------------------------------------
WEBSITE_FEEDS = [
    # South Africa
    ("Springboks / SA Rugby",   "https://www.springboks.rugby/en/news-media/news/rss"),
    ("Bulls",                   "https://bullsrugby.co.za/feed"),
    ("Lions",                   "https://lionsrugby.co.za/feed"),
    ("Sharks",                  "https://sharksrugby.co.za/feed"),
    ("Stormers",                "https://stormers.co.za/feed"),
    # International
    ("All Blacks",              "https://www.allblacks.com/news/rss"),
    ("Ireland Rugby",           "https://www.irishrugby.ie/feed"),
    ("Wales Rugby",             "https://www.wru.wales/feed"),
    ("Scotland Rugby",          "https://scottishrugby.org/news-and-features/feed"),
    ("Argentina Rugby",         "https://www.uar.com.ar/feed"),
    ("Japan Rugby",             "https://en.rugby-japan.jp/feed"),
    ("Tonga Rugby",             "https://www.tonga-rugby-union.com/feed"),
    # URC clubs
    ("Leinster Rugby",          "https://www.leinsterrugby.ie/feed"),
    ("Munster Rugby",           "https://www.munsterrugby.ie/feed"),
    ("Scarlets",                "https://www.scarlets.wales/feed"),
    ("Edinburgh Rugby",         "https://edinburghrugby.org/news-and-features/feed"),
    ("Benetton Rugby",          "https://benettonrugby.it/feed"),
    # English Premiership
    ("Bristol Bears",           "https://www.bristolbearsrugby.com/feed"),
    ("Sale Sharks",             "https://www.salesharks.com/feed"),
    ("Saracens",                "https://saracens.com/feed"),
]

# ---------------------------------------------------------------------------
# YOUTUBE CHANNEL RSS FEEDS  (free, no API key needed)
# Format: https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
# ---------------------------------------------------------------------------
YOUTUBE_CHANNELS = [
    # South Africa
    ("Springboks (BOKTube)",    "UCVI5iqtQOsWZwtAg1o3SIAQ"),
    ("Bulls",                   "UCVdKlS9V0bEyNhDLMnTbvRQ"),
    ("Lions",                   "UCSBzEX42vrPJf-M_eG5XqNA"),
    ("Sharks",                  "UCQoL3-RCoHqjnzFQejXW0Ng"),
    ("Stormers",                "UC5rPh4GAcmJ84vhfgRTQC3w"),
    # International
    ("All Blacks",              "UCsAPiUMyBjtKamxYGbSUnLA"),
    ("Wallabies",               "UC4Y6lpmGz2rkbOVdrOhjgvQ"),
    ("England Rugby",           "UCmi7CahP3G3YySOAFOfSnkw"),
    ("France Rugby",            "UCnH0bSmQqDBfNj9kZzCaINw"),
    ("Ireland Rugby",           "UCn64VUStxkPK06ApqvV_MPA"),
    ("Wales Rugby",             "UCWgLnh6sTHoMnPV6HfGNNfg"),
    ("Scotland Rugby",          "UCycrxh2r7VKKxP-rfa9-cfw"),
    ("Argentina Rugby",         "UCZRmjDMDqGqZckJJf6TGVDQ"),
    ("Fiji Rugby",              "UCQoL3-RCoHqjnzFQejXW0Ng"),
    ("Samoa Rugby",             "UCLb5PHKR3DpWjGjq2kFTv1A"),
    ("Japan Rugby",             "UCl2rFpBWUUbBW0TKFR6I2Vg"),
    ("World Rugby",             "UCE28rwYoaV7jvU6GVzdu_GQ"),
    ("World Rugby Sevens",      "UCmfjIMUteXwYkolTAtALE9g"),
    # URC
    ("Leinster Rugby",          "UCGHjF23GPeIy1eyyBL8Ow2w"),
    ("Munster Rugby",           "UC7991AZNku42o3Y36kUZOJA"),
    ("Ulster Rugby",            "UC4EvohuiwgkUV1v03DDD4eQ"),
    ("Connacht Rugby",          "UCgucukpMfuXvCtG9oELpN1Q"),
    ("Cardiff Rugby",           "UCrVT1pOPraNiimvksjsOgVw"),
    ("Dragons",                 "UCdB_8F9Yqur14jXdSzxyQeA"),
    ("Ospreys",                 "UCJZmXODDzozHonpt08Bok1Q"),
    ("Scarlets",                "UCSpQ51CzUYp_ambKRD7fDCg"),
    ("Edinburgh Rugby",         "UCkyiKiVVlhOTvnYuWMIUgpQ"),
    ("Glasgow Warriors",        "UCBUbMDPGBuHqQlFfHPgqxbw"),
    ("Benetton Rugby",          "UCYLzZ0xgRhRuXXkRkR8gm2w"),
    ("Zebre Parma",             "UC1YlrNry_KQH05fOwROh4_Q"),
    # Premiership
    ("Bath Rugby",              "UCIY0cK57uX_-xm0JUHK3zng"),
    ("Bristol Bears",           "UCySyyTJVcxELIeW83Nmmpjw"),
    ("Exeter Chiefs",           "UCb6NHMYnJE_8UeXKsVDVCEQ"),
    ("Gloucester Rugby",        "UCQCFhiZXUVFUUib0VWe7OuQ"),
    ("Harlequins",              "UC3QXCKORgVOEdKzaxgpzSVg"),
    ("Leicester Tigers",        "UCy3Y-NTbA8DeLzzjw4tRUQA"),
    ("Newcastle Falcons",       "UCCqKNRP-2qIwRh_X7AxDe0Q"),
    ("Northampton Saints",      "UCblNEjRDcaD_8B0pOaJrnog"),
    ("Sale Sharks",             "UC_k3xuhlC_jBgfpJdMqAKxw"),
    ("Saracens",                "UCqhNRDAutbLhJyGfHtFrYmg"),
]

MAX_ITEMS = 5


def fetch_website_feeds():
    items = []
    for team, url in WEBSITE_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:MAX_ITEMS]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()[:250]
                if title and link:
                    items.append({"type": "article", "team": team, "title": title, "link": link, "summary": summary})
        except Exception as e:
            print(f"Warning: {team} website feed failed: {e}")
    return items


def fetch_youtube_feeds():
    items = []
    for team, channel_id in YOUTUBE_CHANNELS:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and link:
                    items.append({"type": "video", "team": team, "title": title, "link": link, "summary": ""})
        except Exception as e:
            print(f"Warning: {team} YouTube feed failed: {e}")
    return items


def categorise(team_name):
    sa = ["Springboks", "Bulls", "Lions", "Sharks", "Stormers", "SA Rugby"]
    intl = ["All Blacks", "Wallabies", "England", "France", "Ireland", "Wales", "Scotland",
            "Argentina", "Fiji", "Samoa", "Japan", "Tonga", "Portugal", "World Rugby",
            "Sevens", "SVNS", "Pumas"]
    for s in sa:
        if s.lower() in team_name.lower():
            return "sa"
    for s in intl:
        if s.lower() in team_name.lower():
            return "international"
    return "club"


def rank_and_format(articles, videos):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")

    articles_text = "\n\n".join(
        f"[ARTICLE] TEAM: {a['team']} | CAT: {categorise(a['team']).upper()}\nTITLE: {a['title']}\nURL: {a['link']}\nSUMMARY: {a['summary']}"
        for a in articles
    )
    videos_text = "\n\n".join(
        f"[VIDEO] TEAM: {v['team']} | CAT: {categorise(v['team']).upper()}\nTITLE: {v['title']}\nURL: {v['link']}"
        for v in videos
    )

    prompt = f"""You are a rugby social media editor. Today is {today}.

Below is official content from rugby team websites and YouTube channels.
Create a polished daily "Rugby Social Digest" email with these sections IN ORDER:

1. 🇿🇦 South African Teams — articles + videos from SA teams, ranked by importance
2. 🌍 International Teams — articles + videos from national teams, ranked by importance
3. 🏉 Club Rugby — articles + videos from URC and Premiership clubs, ranked by importance
4. 🎬 Must-Watch Videos — top 5-8 YouTube videos across all teams worth watching today

Rules:
- Within each section rank by newsworthiness (match news > squad announcements > training > general)
- For articles: show team name bold, hyperlinked headline, 1-sentence summary (your words, max 20 words)
- For videos: show team name bold, hyperlinked video title, emoji 🎬, brief note on what it is
- Skip duplicate stories (same news from multiple sources — keep best version)
- Must-Watch Videos section: pick the most interesting/exciting video titles regardless of section

Output a complete HTML email body (no html/head/body tags):
- Outer wrapper: <div style="font-family: Georgia, serif; max-width: 680px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
- Header: today's date + "Rugby Social Digest" in dark blue (#1a2e4d), bold, 28px
- Each section heading: bold, font-size 18px, border-bottom: 2px solid #e8e8e8, padding-bottom: 4px, margin-top: 28px
- Team name in bold dark green (#1a4d2e) before each item
- Footer in grey: "Delivered daily by Rugby Social Digest Agent"

Then output exactly: ---PLAINTEXT---
Followed by a plain-text version with the same content.

ARTICLES:
{articles_text}

VIDEOS:
{videos_text}"""

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
    sender = "brendennel@gmail.com"
    password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Rugby Social Digest — {today}"
    msg["From"] = f"Rugby Social Digest <{sender}>"
    msg["To"] = sender
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.login(sender, password)
        server.sendmail(sender, sender, msg.as_string())
    print("Email sent successfully.")


def main():
    print("Fetching team website feeds...")
    articles = fetch_website_feeds()
    print(f"Got {len(articles)} articles from {len(WEBSITE_FEEDS)} feeds.")

    print("Fetching YouTube feeds...")
    videos = fetch_youtube_feeds()
    print(f"Got {len(videos)} videos from {len(YOUTUBE_CHANNELS)} channels.")

    if not articles and not videos:
        print("No content found — aborting.")
        return

    print("Ranking and formatting with Claude...")
    html_body, plain_body = rank_and_format(articles, videos)

    print("Sending email...")
    send_email(html_body, plain_body)
    print("Done.")


if __name__ == "__main__":
    main()
