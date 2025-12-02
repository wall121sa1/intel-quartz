from fastapi import APIRouter, Depends, Form
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
        html_parts.append(f"<li>{bot.name} (theme={bot.theme}) - channels: {channel_count}</li>")
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
        html.append(
            f"<tr><td>{ch.telegram_id}</td><td>{ch.language}</td>"
            f"<td>{', '.join(ch.topics)}</td><td>{ch.bot.name}</td></tr>"
        )
    html.append("</table>")
    html.append('<p><a href="/dashboard/channels/new">Add channel</a></p>')
    html.append('<p><a href="/dashboard">Back</a></p>')
    return HTMLResponse("".join(html))


@router.get("/dashboard/channels/new", response_class=HTMLResponse)
def new_channel_form(db: Session = Depends(get_session)):
    bots = db.query(Bot).all()
    options = "".join([f"<option value='{b.id}'>{b.name}</option>" for b in bots])
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
    topics_list = [t.strip() for t in topics.split(",") if t.strip()]
    channel = Channel(
        telegram_id=telegram_id,
        language=language,
        topics=topics_list,
        bot_id=bot_id,
    )
    db.add(channel)
    db.commit()
    return RedirectResponse(url="/dashboard/channels", status_code=303)
