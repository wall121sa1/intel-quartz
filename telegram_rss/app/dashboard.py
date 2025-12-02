import html

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .db import get_session
from .models import Bot, Channel, Feed

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_session)):
    bots = db.query(Bot).all()
    feeds = db.query(Feed).all()
    html_parts = ["<h1>Telegram RSS Dashboard</h1>"]

    html_parts.append("<h2>Bots</h2><ul>")
    for bot in bots:
        channel_count = db.query(Channel).filter_by(bot_id=bot.id).count()
        safe_name = html.escape(bot.name)
        safe_theme = html.escape(bot.theme) if bot.theme else ""
        html_parts.append(
            f"<li>{safe_name} (theme={safe_theme}) - channels: {channel_count}</li>"
        )
    html_parts.append("</ul>")

    html_parts.append('<p><a href="/dashboard/channels">View channels</a></p>')
    html_parts.append('<p><a href="/dashboard/channels/new">Add channel</a></p>')

    html_parts.append("<h2>RSS Feeds</h2><ul>")
    if not feeds:
        html_parts.append("<li>No feeds configured.</li>")
    for feed in feeds:
        safe_language = html.escape(feed.language)
        safe_topic = html.escape(feed.topic)
        rss_url = request.url_for(
            "get_rss", language=feed.language, topic=feed.topic
        )
        safe_url = html.escape(rss_url)
        html_parts.append(
            f"<li>{safe_language}/{safe_topic} - "
            f"<a href=\"{safe_url}\">{safe_url}</a></li>"
        )
    html_parts.append("</ul>")

    return HTMLResponse("".join(html_parts))


@router.get("/dashboard/channels", response_class=HTMLResponse)
def list_channels(db: Session = Depends(get_session)):
    channels = db.query(Channel).all()
    html_parts = ["<h1>Channels</h1><table border='1'>"]
    html_parts.append("<tr><th>telegram_id</th><th>language</th><th>topics</th><th>sensitivity</th><th>bot</th></tr>")
    )
    for ch in channels:
        safe_telegram_id = html.escape(ch.telegram_id)
        safe_language = html.escape(ch.language)
        safe_topics = ", ".join(html.escape(t) for t in ch.topics)
        safe_bot = html.escape(ch.bot.name)
        safe_sensitivity = html.escape(ch.sensitivity)
        html_parts.append(
            f"<tr><td>{safe_telegram_id}</td><td>{safe_language}</td>"
            f"<td>{safe_topics}</td><td>{safe_bot}</td>"
             f"<td>{safe_sensitivity}</td></tr>"
        )
    html_parts.append("</table>")
    html_parts.append('<p><a href="/dashboard/channels/new">Add channel</a></p>')
    html_parts.append('<p><a href="/dashboard">Back</a></p>')
    return HTMLResponse("".join(html_parts))


@router.get("/dashboard/channels/new", response_class=HTMLResponse)
def new_channel_form(db: Session = Depends(get_session)):
    bots = db.query(Bot).all()
    options = "".join([f"<option value='{b.id}'>{b.name}</option>" for b in bots])
    html = f"""
    <h1>Add Channel</h1>
    <form method="post" action="/dashboard/channels">
      <label>Telegram ID (e.g. @mychannel or numeric): <input name="telegram_id"></label><br>
      <label>Language (e.g. ru, en, fa): <input name="language" value="unknown"></label><br>
      <label>Topics (comma-separated): <input name="topics" value="unclassified"></label><br>
      <label>Sensitivity:
        <select name="sensitivity">
          <option value="public">Public</option>
          <option value="sensitive">Sensitive</option>
        </select>
      </label><br>
      <label>Bot: <select name="bot_id">{options}</select></label><br>
      <button type="submit">Add</button>
    </form>
    <p><a href="/dashboard">Back</a></p>
    """
    return HTMLResponse(html)



@router.post("/dashboard/channels")
def create_channel(
    telegram_id: str = Form(...),
    language: str = Form(...),
    topics: str = Form(...),
    sensitivity: str = Form("public"),
    bot_id: int = Form(...),
    db: Session = Depends(get_session),
):
    topics_list = [t.strip() for t in topics.split(",") if t.strip()]
    channel = Channel(
        telegram_id=telegram_id,
        language=language,
        topics=topics_list,
        bot_id=bot_id,
        sensitivity=sensitivity,
    )
    db.add(channel)
    db.commit()

    # ensure feeds exist for each topic (if you added that helper earlier)
    # for topic in topics_list:
    #     ensure_feed_exists(db, language, topic)

    return RedirectResponse(url="/dashboard/channels", status_code=303)

