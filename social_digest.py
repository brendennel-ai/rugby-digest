#!/usr/bin/env python3
import os
import json
import urllib.request
import urllib.parse
import anthropic
from datetime import datetime, timezone

BEARER_TOKEN = os.environ["TWITTER_BEARER_TOKEN"]

SA_TEAMS = ["Springboks","BlueBullsRugby","LionsRugbyCo","SharksRugby","TheStormers"]
INTERNATIONAL_TEAMS = ["AllBlacks","WallabiesRugby","EnglandRugby","FranceRugby","IrishRugby","WalesRugby","ScotlandRugby","ArgentinaRugby","FijiRugby","manusamoa","PortugalRugby","TongaRugby","JRFURugby","WorldRugby","WorldRugby7s"]
URC_CLUBS = ["LeinsterRugby","MunsterRugby","UlsterRugby","connachtrugby","Cardiff_Rugby","dragonsrugby","ospreys","scarlets_rugby","EdinburghRugby","GlasgowWarriors","BenettonRugby","ZebreParma","BlueBullsRugby","LionsRugbyCo","SharksRugby","TheStormers"]
PREMIERSHIP_CLUBS = ["bathrugby","BristolBears","ExeterChiefs","gloucesterrugby","Harlequins","LeicesterTigers","FalconsRugby","SaintsRugby","SaleSharksMC","Saracens"]
ALL_ACCOUNTS = list(dict.fromkeys(SA_TEAMS + INTERNATIONAL_TEAMS + URC_CLUBS + PREMIERSHIP_CLUBS))
MAX_TWEETS_PER_ACCOUNT = 5

def twitter_request(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {BEARER_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP error {e.code} for {url}: {e.read().decode()[:200]}")
        return None

def get_user_ids(usernames):
    user_map = {}
    for i in range(0, len(usernames), 100):
        batch = usernames[i:i+100]
        params = urllib.parse.urlencode({"usernames": ",".join(batch), "user.fields": "id,name,username"})
        data = twitter_request(f"https://api.twitter.com/2/users/by?{params}")
        if data and "data" in data:
            for user in data["data"]:
                user_map[user["username"].lower()] = user
    return user_map

def get_tweets_for_user(user_id, username):
    params = urllib.parse.urlencode({"max_results": MAX_TWEETS_PER_ACCOUNT, "exclude": "replies,retweets", "tweet.fields": "created_at,public_metrics,text"})
    data = twitter_request(f"https://api.twitter.com/2/users/{user_id}/tweets?{params}")
    tweets = []
    if data and "data" in data:
        for t in data["data"]:
            metrics = t.get("public_metrics", {})
            tweets.append({"username": username, "tweet_id": t["id"], "text": t["text"], "created_at": t.get("created_at", ""), "likes": metrics.get("like_count", 0), "retweets": metrics.get("retweet_count", 0), "url": f"https://twitter.com/{username}/status/{t['id']}"})
    return tweets

def fetch_all_tweets(user_map):
    all_tweets = {"sa": [], "international": [], "urc": [], "premiership": []}
    seen = set()
    def fetch(handles, key):
        for h in handles:
            if h.lower() in seen: continue
            user = user_map.get(h.lower())
            if not user: print(f"Warning: could not find @{h}"); continue
            all_tweets[key].extend(get_tweets_for_user(user["id"], user["username"]))
            seen.add(h.lower())
    fetch(SA_TEAMS, "sa")
    fetch(INTERNATIONAL_TEAMS, "international")
    fetch([h for h in URC_CLUBS if h.lower() not in seen], "urc")
    fetch([h for h in PREMIERSHIP_CLUBS if h.lower() not in seen], "premiership")
    return all_tweets

def format_tweets_for_prompt(all_tweets):
    lines = []
    for group, label in [("sa","SOUTH AFRICA"),("international","INTERNATIONAL"),("urc","URC CLUBS"),("premiership","PREMIERSHIP CLUBS")]:
        lines.append(f"\n=== {label} ===")
        for t in all_tweets[group]:
            lines.append(f"@{t['username']} | Likes:{t['likes']} RT:{t['retweets']} | {t['created_at'][:10] if t['created_at'] else 'today'}\n{t['text']}\nURL: {t['url']}")
    return "\n\n".join(lines)

def rank_and_format(all_tweets):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    tweets_text = format_tweets_for_prompt(all_tweets)
    prompt = f"""You are a rugby social media editor. Today is {today}.

Below are recent tweets from official rugby team accounts grouped by tier.
Curate and present the most interesting content as a daily social media digest email.

Rules:
- Prioritise: South African teams first, then international, then clubs
- Within each group rank by importance (match news > announcements > training > general)
- Pick a Trending & Funny section: highest engagement or most entertaining tweets regardless of tier
- Skip pure promotional/sponsor posts unless newsworthy

Output a complete HTML email body (no html/head/body tags):
- Outer wrapper: <div style="font-family: Georgia, serif; max-width: 680px; margin: 0 auto; color: #1a1a1a; line-height: 1.6;">
- Header: today's date + "Rugby Social Digest" in dark blue (#1a2e4d), bold, 28px
- Sections in order: 1) South African Teams 2) International Teams 3) Club Rugby (URC & Premiership) 4) Trending & Funny
- Each section: bold heading with border-bottom: 2px solid #e8e8e8
- Each tweet: @handle bold, hyperlinked tweet, engagement stats in grey, 1-sentence summary
- Footer in grey: "Delivered daily by Rugby Social Digest Agent"

Then output exactly: ---PLAINTEXT---
Followed by plain-text version.

TWEETS:
{tweets_text}"""
    msg = client.messages.create(model="claude-opus-4-7", max_tokens=4096, messages=[{"role": "user", "content": prompt}])
    full = msg.content[0].text
    if "---PLAINTEXT---" in full:
        html, plain = full.split("---PLAINTEXT---", 1)
    else:
        html, plain = full, full
    return html.strip(), plain.strip()

def send_email(html_body, plain_body):
    import smtplib, ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
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
    print("Resolving Twitter usernames...")
    user_map = get_user_ids(ALL_ACCOUNTS)
    print(f"Resolved {len(user_map)} accounts.")
    print("Fetching tweets...")
    all_tweets = fetch_all_tweets(user_map)
    total = sum(len(v) for v in all_tweets.values())
    print(f"Fetched {total} tweets total.")
    if total == 0:
        print("No tweets found — aborting.")
        return
    print("Ranking and formatting with Claude...")
    html_body, plain_body = rank_and_format(all_tweets)
    print("Sending email...")
    send_email(html_body, plain_body)
    print("Done.")

if __name__ == "__main__":
    main()
