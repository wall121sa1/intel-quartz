import html

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .db import get_session
from .models import Bot, Channel

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_session)):
    bots = db.query(Bot).all()
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

    return HTMLResponse("".join(html_parts))


@router.get("/dashboard/channels", response_class=HTMLResponse)
def list_channels(db: Session = Depends(get_session)):
    channels = db.query(Channel).all()
    html = ["<h1>Channels</h1><table border='1'>"]
    html.append("<tr><th>telegram_id</th><th>language</th><th>topics</th><th>bot</th></tr>")
    for ch in channels:
        safe_telegram_id = html.escape(ch.telegram_id)
        safe_language = html.escape(ch.language)
        safe_topics = ", ".join(html.escape(t) for t in ch.topics)
        safe_bot = html.escape(ch.bot.name)
        html.append(
            f"<tr><td>{safe_telegram_id}</td><td>{safe_language}</td>"
            f"<td>{safe_topics}</td><td>{safe_bot}</td></tr>"
        )
    html.append("</table>")
    html.append('<p><a href="/dashboard/channels/new">Add channel</a></p>')
    html.append('<p><a href="/dashboard">Back</a></p>')
    return HTMLResponse("".join(html))


@router.get("/dashboard/channels/new", response_class=HTMLResponse)
def new_channel_form(db: Session = Depends(get_session)):
    bots = db.query(Bot).all()
    options = "".join(
        [f"<option value='{b.id}'>{html.escape(b.name)}</option>" for b in bots]
    )
    html = f"""
    <h1>Add Channel</h1>
    <form method="post" action="/dashboard/channels">
      <label>Telegram ID (e.g. @mychannel): <input name="telegram_id"></label><br>
      <label>Language (e.g. ru, en, fa): <input name="language"></label><br>
      <label>Topics (comma-separated): <input name="topics"></label><br>
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
    bot_id: int = Form(...),
    db: Session = Depends(get_session),
):
    telegram_id = telegram_id.strip()
    language = language.strip()
    topics_list = [t.strip() for t in topics.split(",") if t.strip()]

    if not telegram_id or not language or not topics_list:
        raise HTTPException(status_code=400, detail="Missing required fields")

    bot = db.query(Bot).filter_by(id=bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    channel = Channel(
        telegram_id=telegram_id,
        language=language,
        topics=topics_list,
        bot_id=bot_id,
    )
    db.add(channel)
    db.commit()
    return RedirectResponse(url="/dashboard/channels", status_code=303)
