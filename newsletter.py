import os
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import requests

# --- Config ---
NEWSAPI_KEY = os.environ["NEWSAPI_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

RECIPIENT_EMAIL = "nick.valiton@synapsesem.com"
SENDER_EMAIL = GMAIL_ADDRESS  # Gmail SMTP requires sender to match authenticated account

KEYWORDS = [
    "AI search",
    "AI search engine",
    "Google AI Overviews",
    "SearchGPT",
    "Perplexity AI",
    "Bing Copilot search",
    "generative search",
    "AI SEO",
]


def fetch_newsapi_articles():
    """Fetch articles from NewsAPI for each keyword."""
    articles = []
    from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    for keyword in KEYWORDS:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f'"{keyword}"',
            "from": from_date,
            "sortBy": "relevancy",
            "language": "en",
            "pageSize": 5,
            "apiKey": NEWSAPI_KEY,
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            articles.extend(data.get("articles", []))

    # Deduplicate by URL
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)

    return unique


def fetch_google_news_rss():
    """Fetch articles from Google News RSS for AI search topics."""
    queries = ["AI+search+trends", "AI+search+engine", "Google+AI+Overviews+SEO"]
    articles = []

    for query in queries:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                articles.append({
                    "title": title,
                    "url": link,
                    "publishedAt": pub_date,
                    "source": {"name": "Google News"},
                    "description": "",
                })

    return articles


def format_articles_for_prompt(articles):
    """Format article list into a plain text block for the Claude prompt."""
    lines = []
    for i, a in enumerate(articles[:30], 1):  # Cap at 30 articles
        title = a.get("title") or ""
        source = a.get("source", {}).get("name") or "Unknown"
        date = a.get("publishedAt") or ""
        desc = a.get("description") or ""
        url = a.get("url") or ""
        lines.append(f"{i}. [{source}] {title}\n   {date}\n   {desc}\n   {url}")
    return "\n\n".join(lines)


def generate_newsletter(articles):
    """Use Claude to summarize articles into a newsletter."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    article_text = format_articles_for_prompt(articles)
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    prompt = f"""You are an expert SEO and AI search analyst writing a weekly newsletter for Nick Valiton,
Associate Director of SEO at Synapse SEM in Boston. Nick manages SEO strategy for a portfolio of clients
across various industries and needs to stay ahead of how AI search changes are affecting organic visibility,
click-through rates, and search strategy.

Today is {today}. Here are this week's news articles about AI search trends:

{article_text}

Write a professional, actionable weekly newsletter called "AI Search Weekly" with the following structure:

1. A short intro (2-3 sentences) summarizing the week's most important theme for SEO professionals.

2. "This Week's Top Stories" — 4-6 stories, each formatted as:
   - A bold, linked headline using the article's URL: <a href="URL"><strong>Headline</strong></a>
   - Source name and date in muted text
   - 1-2 sentences on what happened
   - A "Why it matters for SEO:" line explaining the direct implication for client SEO strategy
     (e.g. impact on organic CTR, content strategy, SERP visibility, crawling/indexing, etc.)

3. "Key Takeaways for Your Clients This Week" — 3 concise, actionable bullets an SEO strategist
   can act on or bring to a client meeting. Be specific — not generic advice.

4. A one-line sign-off from "AI Search Weekly"

Format cleanly for an HTML email. Use <h2>, <h3>, <p>, <ul>, <li>, <strong>, and <a> tags.
Do not include <html>, <head>, or <body> tags — just the inner content.
Tone: sharp, direct, and built for a senior SEO practitioner who values brevity and strategy over hype."""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def send_email(newsletter_html):
    """Send the newsletter via Gmail SMTP using an app password."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    message = MIMEMultipart("alternative")
    message["Subject"] = f"AI Search Weekly: {today}"
    message["From"] = SENDER_EMAIL
    message["To"] = RECIPIENT_EMAIL

    message.attach(MIMEText(newsletter_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(message)

    print(f"Email sent from {SENDER_EMAIL} to {RECIPIENT_EMAIL}")


def main():
    print("Fetching articles from NewsAPI...")
    newsapi_articles = fetch_newsapi_articles()
    print(f"  Found {len(newsapi_articles)} articles from NewsAPI")

    print("Fetching articles from Google News RSS...")
    rss_articles = fetch_google_news_rss()
    print(f"  Found {len(rss_articles)} articles from Google News RSS")

    all_articles = newsapi_articles + rss_articles

    if not all_articles:
        print("No articles found. Exiting.")
        return

    print(f"Generating newsletter from {len(all_articles)} total articles...")
    newsletter_html = generate_newsletter(all_articles)

    print("Sending email...")
    send_email(newsletter_html)
    print("Done!")


if __name__ == "__main__":
    main()
