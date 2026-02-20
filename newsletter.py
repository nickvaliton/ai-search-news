import os
import requests
import anthropic
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# --- Config ---
NEWSAPI_KEY = os.environ["NEWSAPI_KEY"]
SENDGRID_API_KEY = os.environ["SENDGRID_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

RECIPIENT_EMAIL = "nick.valiton@synapsesem.com"
SENDER_EMAIL = "nickvaliton@gmail.com"  # Must match your verified SendGrid sender

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
    from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

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
    import xml.etree.ElementTree as ET

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
    today = datetime.utcnow().strftime("%B %d, %Y")

    prompt = f"""You are an expert SEO and AI search analyst writing a weekly newsletter for Nick Valiton,
Associate Director of SEO at Synapse SEM in Boston.

Today is {today}. Here are this week's news articles about AI search trends:

{article_text}

Write a professional, engaging weekly newsletter called "AI Search Weekly" with the following structure:

1. A short intro (2-3 sentences) summarizing the week's biggest theme
2. "This Week's Top Stories" — 4-6 bullet points, each with a bold headline and 1-2 sentence summary. Include the source name.
3. "What This Means for SEO" — 2-3 practical takeaways for SEO professionals
4. A closing line signing off as "AI Search Weekly"

Format it cleanly for an HTML email. Use <h2>, <h3>, <p>, <ul>, <li>, and <strong> tags.
Do not include <html>, <head>, or <body> tags — just the inner content.
Keep the tone sharp, professional, and useful for a senior SEO practitioner."""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def send_email(html_content):
    """Send the newsletter via SendGrid."""
    today = datetime.utcnow().strftime("%B %d, %Y")
    subject = f"AI Search Weekly — {today}"

    # Wrap in basic HTML shell
    full_html = f"""
    <html>
    <body style="font-family: Georgia, serif; max-width: 640px; margin: 0 auto; padding: 24px; color: #1a1a1a; line-height: 1.6;">
        {html_content}
        <hr style="margin-top: 40px; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: #888;">You're receiving this because you set it up. Unsubscribe? Just delete the GitHub Action.</p>
    </body>
    </html>
    """

    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=RECIPIENT_EMAIL,
        subject=subject,
        html_content=full_html,
    )

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)
    print(f"Email sent. Status code: {response.status_code}")


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
