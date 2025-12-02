from typing import List

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .db import get_session
from .models import Bot, Channel, Feed, FeedItem
from .dialog_sync import sync_dialogs_for_bot
from .release_scheduler import run_release_cycle_once

router = APIRouter()


# ---------- helpers for simple templating ----------

BASE_STYLE = """
<style>
  body {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0f172a;
    color: #e5e7eb;
    margin: 0;
    padding: 0;
  }
  a { color: #38bdf8; text-decoration: none; }
  a:hover { text-decoration: underline; }

  .page {
    max-width: 1000px;
    margin: 0 auto;
    padding: 24px 16px 40px;
  }
  .header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .title {
    font-size: 24px;
    font-weight: 600;
  }
  .subtitle {
    font-size: 14px;
    color: #9ca3af;
  }
  .nav {
    margin-bottom: 20px;
  }
  .nav a {
    margin-right: 12px;
    font-size: 14px;
  }

  .card {
    background: #020617;
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 10px 25px rgba(15,23,42,0.7);
    border: 1px solid #1f2937;
    margin-bottom: 18px;
  }

  .card h2 {
    margin: 0 0 8px 0;
    font-size: 18px;
  }

  .card h3 {
    margin: 0 0 8px 0;
    font-size: 16px;
  }

  .btn {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 999px;
    border: none;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    background: #38bdf8;
    color: #0f172a;
  }
  .btn-secondary {
    background: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
  }
  .btn-danger {
    background: #ef4444;
    color: #fee2e2;
  }

  .btn-sm {
    padding: 4px 8px;
    font-size: 12px;
  }

  .pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
  }
  .pill-green {
    background: #064e3b;
    color: #6ee7b7;
  }
  .pill-yellow {
    background: #78350f;
    color: #facc15;
  }
  .pill-red {
    background: #7f1d1d;
    color: #fecaca;
  }
  .pill-gray {
    background: #111827;
    color: #9ca3af;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
  }
  th, td {
    padding: 8px 6px;
    font-size: 13px;
    border-bottom: 1px solid #1f2937;
    vertical-align: top;
  }
  th {
    text-align: left;
    font-weight: 500;
    color: #9ca3af;
  }
  tr:hover td {
    background: rgba(15,23,42,0.6);
  }

  form.inline {
    display: inline;
  }

  .field-label {
    font-size: 13px;
    color: #9ca3af;
    margin-bottom: 4px;
  }
  .field-input, select {
    width: 100%;
    padding: 6px 8px;
    border-radius: 8px;
    border: 1px solid #374151;
    background: #020617;
    color: #e5e7eb;
    font-size: 13px;
    margin-bottom: 10px;
  }
  .field-input:focus, select:focus {
    outline: none;
    border-color: #38bdf8;
    box-shadow: 0 0 0 1px rgba(56,189,248,0.5);
  }

  .two-column {
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 18px;
  }

  .hint {
    font-size: 12px;
    color: #9ca3af;
  }
</style>
"""

def wrap_page(content: str, title: str = "Telegram RSS Dashboard") -> str:
    return f"""
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  {BASE_STYLE}
</head>
<body>
  <div class="page">
    <div class="header">
      <div>
        <div class="title">Telegram RSS</div>
        <div class="subtitle">Bots, channels & feeds</div>
      </div>
      <div class="nav">
        <a href="/dashboard">Overview</a>
        <a href="/dashboard/channels">Channels</a>
        <a href="/dashboard/channels/new">Add channel</a>
      </div>
    </div>
    {content}
  </div>
</body>
</html>
"""


# ---------- routes ----------

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_session)):
    bots: List[Bot] = db.query(Bot).all()
    feeds: List[Feed] = db.query(Feed).all()

    # ---- Bot cards ----
    bot_cards = []
    for bot in bots:
        channel_count = db.query(Channel).filter_by(bot_id=bot.id).count()
        enabled_label = '<span class="pill pill-green">enabled</span>' if bot.enabled else '<span class="pill pill-gray">disabled</span>'
        theme = bot.theme or "–"

        bot_html = f"""
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <h2>{bot.name}</h2>
              <div class="hint">Theme: {theme}</div>
              <div class="hint">Channels: {channel_count}</div>
            </div>
            <div>
              {enabled_label}
            </div>
          </div>
          <div style="margin-top:10px;">
            <form class="inline" method="post" action="/dashboard/bots/{bot.name}/sync">
              <button class="btn btn-sm" type="submit">Sync dialogs → channels</button>
            </form>
          </div>
        </div>
        """
        bot_cards.append(bot_html)

    if not bot_cards:
        bot_cards.append(
            "<div class='card'><div>No bots configured yet. Add them in config.yaml.</div></div>"
        )

    # ---- Feeds card ----
    feed_rows = []
    for feed in feeds:
        # Count items for a quick sense of “activity”
        item_count = db.query(FeedItem).filter(FeedItem.feed_id == feed.id).count()
        url_path = f"/rss/{feed.language}/{feed.topic}"
        feed_rows.append(f"""
        <tr>
          <td>{feed.language}</td>
          <td>{feed.topic}</td>
          <td>{feed.slug}</td>
          <td>{item_count}</td>
          <td><a href="{url_path}" target="_blank">{url_path}</a></td>
        </tr>
        """)

    if not feed_rows:
        feeds_table = """
        <p class="hint">No feeds yet. Add channels with language + topics, and release scheduler will create feeds automatically.</p>
        """
    else:
        feeds_table = f"""
        <table>
          <thead>
            <tr>
              <th>Language</th>
              <th>Topic</th>
              <th>Slug</th>
              <th>Items</th>
              <th>RSS URL</th>
            </tr>
          </thead>
          <tbody>
            {''.join(feed_rows)}
          </tbody>
        </table>
        """

    feeds_card = f"""
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <div>
          <h2>Active RSS Feeds</h2>
          <p class="hint">
            These feeds are addressable under your server base URL, e.g.
            <code>http://localhost:2000/&lt;path&gt;</code>. Use the links below in your other project.
          </p>
        </div>
        <div>
          <form class="inline" method="post" action="/dashboard/feeds/release">
            <button class="btn btn-sm btn-secondary" type="submit">Run release now</button>
          </form>
        </div>
      </div>
      {feeds_table}
    </div>
    """

    html = """
    <div class="card">
      <h2>Overview</h2>
      <p class="hint">
        Use the cards below to sync dialogs from each Telegram account into channels,
        then refine language, topics and sensitivity on the Channels page.
      </p>
    </div>
    """ + "".join(bot_cards) + feeds_card

    return HTMLResponse(wrap_page(html, "Telegram RSS – Dashboard"))


@router.post("/dashboard/bots/{bot_name}/sync")
async def sync_bot_dialogs(bot_name: str, db: Session = Depends(get_session)):
    # Run async dialog sync for this bot
    try:
        imported = await sync_dialogs_for_bot(bot_name, import_new=True)
        print(f"[dashboard] Synced dialogs for {bot_name}, imported {imported} new channels.")
    except Exception as e:
        print(f"[dashboard] Error syncing dialogs for {bot_name}: {e}")

    # Redirect to channels view so user can see new entries
    return RedirectResponse(url="/dashboard/channels", status_code=303)


@router.get("/dashboard/channels", response_class=HTMLResponse)
def list_channels(db: Session = Depends(get_session)):
    channels: List[Channel] = db.query(Channel).all()

    rows = []
    for ch in channels:
        topics_str = ", ".join(ch.topics) if ch.topics else ""
        sensitivity_pill = (
            '<span class="pill pill-green">public</span>'
            if ch.sensitivity == "public"
            else '<span class="pill pill-yellow">sensitive</span>'
        )
        enabled_pill = (
            '<span class="pill pill-green">enabled</span>'
            if ch.enabled
            else '<span class="pill pill-red">disabled</span>'
        )
        display_name = ch.display_name or "–"
        numeric_id = ch.telegram_numeric_id or "–"

        rows.append(f"""
        <tr>
          <td>{ch.id}</td>
          <td>{display_name}</td>
          <td>{ch.telegram_id}</td>
          <td>{numeric_id}</td>
          <td>{ch.bot.name if ch.bot else '–'}</td>
          <td>{ch.language}</td>
          <td>{topics_str}</td>
          <td>{sensitivity_pill}</td>
          <td>{enabled_pill}</td>
          <td>
            <a href="/dashboard/channels/{ch.id}/edit" class="btn btn-sm btn-secondary">Edit</a>
          </td>
        </tr>
        """)

    table_html = f"""
    <div class="card">
      <h2>Channels</h2>
      <p class="hint">
        These are the chats/groups/channels your Telegram accounts will ingest. Edit language,
        topics and sensitivity here. Only <b>enabled</b> channels are polled.
      </p>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Telegram @</th>
            <th>Telegram #ID</th>
            <th>Bot</th>
            <th>Language</th>
            <th>Topics</th>
            <th>Sensitivity</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows) if rows else '<tr><td colspan="10">No channels yet. Sync dialogs from a bot or add one manually.</td></tr>'}
        </tbody>
      </table>
    </div>
    """

    return HTMLResponse(wrap_page(table_html, "Telegram RSS – Channels"))


@router.get("/dashboard/channels/new", response_class=HTMLResponse)
def new_channel_form(db: Session = Depends(get_session)):
    bots = db.query(Bot).all()
    options = "".join([f"<option value='{b.id}'>{b.name}</option>" for b in bots])

    form_html = f"""
    <div class="two-column">
      <div class="card">
        <h2>Add Channel</h2>
        <form method="post" action="/dashboard/channels">
          <div class="field-label">Telegram ID (e.g. @mychannel or numeric dialog ID)</div>
          <input class="field-input" name="telegram_id" placeholder="@mychannel">

          <div class="field-label">Telegram numeric ID (optional)</div>
          <input class="field-input" name="telegram_numeric_id" placeholder="123456789" type="number">

          <div class="field-label">Display name (optional)</div>
          <input class="field-input" name="display_name" placeholder="Channel or group name">

          <div class="field-label">Language (e.g. en, ru, fa)</div>
          <input class="field-input" name="language" value="unknown">

          <div class="field-label">Topics (comma-separated)</div>
          <input class="field-input" name="topics" value="unclassified">

          <div class="field-label">Sensitivity</div>
          <select name="sensitivity">
            <option value="public">Public</option>
            <option value="sensitive">Sensitive</option>
          </select>

          <div class="field-label">Bot</div>
          <select name="bot_id">
            {options}
          </select>

          <div style="margin-top:10px;">
            <button class="btn" type="submit">Add channel</button>
          </div>
        </form>
      </div>
      <div class="card">
        <h3>Tips</h3>
        <p class="hint">
          If you've already joined groups/channels from the Telegram app, use
          the <b>Sync dialogs → channels</b> button on the main dashboard to pull
          them in automatically, then refine language/topics here.
        </p>
      </div>
    </div>
    """

    return HTMLResponse(wrap_page(form_html, "Telegram RSS – Add Channel"))


@router.post("/dashboard/channels")
def create_channel(
    telegram_id: str = Form(...),
    telegram_numeric_id: str = Form(None),
    display_name: str = Form(""),
    language: str = Form(...),
    topics: str = Form(...),
    sensitivity: str = Form("public"),
    bot_id: int = Form(...),
    db: Session = Depends(get_session),
):
    topics_list = [t.strip() for t in topics.split(",") if t.strip()]
    numeric_id = int(telegram_numeric_id) if telegram_numeric_id else None
    channel = Channel(
        telegram_id=telegram_id,
        telegram_numeric_id=numeric_id,
        display_name=display_name or telegram_id,
        language=language,
        topics=topics_list,
        bot_id=bot_id,
        sensitivity=sensitivity,
        enabled=True,
    )
    db.add(channel)
    db.commit()
    return RedirectResponse(url="/dashboard/channels", status_code=303)


@router.get("/dashboard/channels/{channel_id}/edit", response_class=HTMLResponse)
def edit_channel_form(channel_id: int, db: Session = Depends(get_session)):
    ch: Channel = db.query(Channel).filter_by(id=channel_id).first()
    if not ch:
        return HTMLResponse(wrap_page("<div class='card'>Channel not found.</div>", "Edit Channel"), status_code=404)

    bots = db.query(Bot).all()
    bot_options = "".join([
        f"<option value='{b.id}' {'selected' if b.id == ch.bot_id else ''}>{b.name}</option>"
        for b in bots
    ])

    topics_str = ", ".join(ch.topics) if ch.topics else ""
    numeric_id_value = ch.telegram_numeric_id if ch.telegram_numeric_id is not None else ""

    form_html = f"""
    <div class="card">
      <h2>Edit Channel</h2>
      <form method="post" action="/dashboard/channels/{ch.id}/edit">
        <div class="field-label">Telegram ID</div>
        <input class="field-input" name="telegram_id" value="{ch.telegram_id}" readonly>

        <div class="field-label">Telegram numeric ID</div>
        <input class="field-input" name="telegram_numeric_id" value="{numeric_id_value}" type="number">

        <div class="field-label">Display name</div>
        <input class="field-input" name="display_name" value="{ch.display_name or ''}">

        <div class="field-label">Language</div>
        <input class="field-input" name="language" value="{ch.language}">

        <div class="field-label">Topics (comma-separated)</div>
        <input class="field-input" name="topics" value="{topics_str}">

        <div class="field-label">Sensitivity</div>
        <select name="sensitivity">
          <option value="public" {'selected' if ch.sensitivity == 'public' else ''}>Public</option>
          <option value="sensitive" {'selected' if ch.sensitivity == 'sensitive' else ''}>Sensitive</option>
        </select>

        <div class="field-label">Status</div>
        <select name="enabled">
          <option value="true" {'selected' if ch.enabled else ''}>Enabled</option>
          <option value="false" {'selected' if not ch.enabled else ''}>Disabled</option>
        </select>

        <div class="field-label">Bot</div>
        <select name="bot_id">
          {bot_options}
        </select>

        <div style="margin-top:10px;">
          <button class="btn" type="submit">Save changes</button>
          <a href="/dashboard/channels" class="btn btn-secondary btn-sm" style="margin-left:8px;">Cancel</a>
        </div>
      </form>
    </div>
    """

    return HTMLResponse(wrap_page(form_html, "Telegram RSS – Edit Channel"))

@router.post("/dashboard/feeds/release")
async def manual_release():
    try:
        await run_release_cycle_once()
        print("[dashboard] Manual release cycle triggered from UI.")
    except Exception as e:
        print(f"[dashboard] Error running manual release: {e}")
    # Redirect back to dashboard so user sees updated feed list
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/dashboard/channels/{channel_id}/edit")
def update_channel(
    channel_id: int,
    telegram_numeric_id: str = Form(None),
    display_name: str = Form(""),
    language: str = Form(...),
    topics: str = Form(...),
    sensitivity: str = Form("public"),
    enabled: str = Form("true"),
    bot_id: int = Form(...),
    db: Session = Depends(get_session),
):
    ch: Channel = db.query(Channel).filter_by(id=channel_id).first()
    if not ch:
        return RedirectResponse(url="/dashboard/channels", status_code=303)

    topics_list = [t.strip() for t in topics.split(",") if t.strip()]
    numeric_id = int(telegram_numeric_id) if telegram_numeric_id else None

    ch.language = language
    ch.topics = topics_list
    ch.sensitivity = sensitivity
    ch.enabled = (enabled.lower() == "true")
    ch.bot_id = bot_id
    ch.telegram_numeric_id = numeric_id
    ch.display_name = display_name or ch.telegram_id

    db.commit()
    return RedirectResponse(url="/dashboard/channels", status_code=303)
