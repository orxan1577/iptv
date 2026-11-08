import os
import sqlite3
import secrets

from flask import Flask, request, redirect, session, Response, url_for
from markupsafe import escape
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-demo-key")

ADMIN_USER = os.environ.get("ADMIN_USER", "orxan")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "change-this-password")
DB = "iptv.db"


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL
        )
        """)
        db.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            expires TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL
        )
        """)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (request.form.get("username") == ADMIN_USER
                and request.form.get("password") == ADMIN_PASS):
            session["login"] = True
            return redirect("/")
    return """
    <h2>ORXAN IPTV PANEL</h2>
    <form method="post">
    <input name="username" placeholder="Admin login">
    <input name="password" type="password" placeholder="Admin parol">
    <button>Giriş</button>
    </form>
    """


@app.route("/")
def home():
    if not session.get("login"):
        return redirect("/login")

    with connect() as db:
        channels = db.execute("SELECT * FROM channels").fetchall()
        customers = db.execute("SELECT * FROM customers").fetchall()

    html = """
    <h1>ORXAN IPTV PANEL</h1>
    <a href="/logout">Çıxış</a>
    <hr>
    <h2>Kanal əlavə et</h2>
    <form action="/kanal" method="post">
    <input name="name" placeholder="Kanal adı" required>
    <input name="url" placeholder="Yayım linki" required>
    <button>Əlavə et</button>
    </form>
    <h3>Kanallar</h3>
    """

    for c in channels:
        html += (
            f"<p>{escape(c['name'])} "
            f"<a href='/izle/{c['id']}'>İzlə</a> "
            f"<a href='/kanal-sil/{c['id']}'>Sil</a></p>"
        )

    html += """
    <hr>
    <h2>Müştəri yarat</h2>
    <form action="/musteri" method="post">
    <input name="name" placeholder="Müştəri adı" required>
    <input name="username" placeholder="Login" required>
    <input name="password" type="password" placeholder="Parol" required>
    <select name="days">
    <option value="30">30 gün</option>
    <option value="90">90 gün</option>
    <option value="180">180 gün</option>
    <option value="365">365 gün</option>
    </select>
    <button>Yarat</button>
    </form>
    <h3>Müştərilər</h3>
    """

    for c in customers:
        link = url_for("playlist", token=c["token"], _external=True)
        html += (
            f"<p>Ad: {escape(c['name'])}<br>"
            f"Login: {escape(c['username'])}<br>"
            f"Bitmə: {escape(c['expires'])}<br>"
            f"M3U: <a href='{escape(link)}'>Playlist linki</a></p><hr>"
        )

    return html


@app.route("/kanal", methods=["POST"])
def kanal():
    if not session.get("login"):
        return redirect("/login")

    with connect() as db:
        db.execute(
            "INSERT INTO channels (name, url) VALUES (?, ?)",
            (request.form["name"], request.form["url"])
        )
    return redirect("/")


@app.route("/izle/<int:i>")
def izle(i):
    if not session.get("login"):
        return redirect("/login")

    with connect() as db:
        c = db.execute(
            "SELECT * FROM channels WHERE id=?", (i,)
        ).fetchone()

    if not c:
        return "Kanal tapılmadı", 404

    return f"<h2>{escape(c['name'])}</h2><a href='/'>Geri</a>"


@app.route("/kanal-sil/<int:i>")
def kanal_sil(i):
    if not session.get("login"):
        return redirect("/login")

    with connect() as db:
        db.execute("DELETE FROM channels WHERE id=?", (i,))
    return redirect("/")


@app.route("/musteri", methods=["POST"])
def musteri():
    if not session.get("login"):
        return redirect("/login")

    username = request.form["username"].strip()
    password_hash = generate_password_hash(request.form["password"])
    days = int(request.form["days"])
    expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    token = secrets.token_urlsafe(32)

    try:
        with connect() as db:
            db.execute(
                """INSERT INTO customers
                (name, username, password_hash, expires, token)
                VALUES (?, ?, ?, ?, ?)""",
                (request.form["name"], username, password_hash, expires, token)
            )
    except sqlite3.IntegrityError:
        return "Bu login artıq mövcuddur."

    return redirect("/")


@app.route("/musteri-giris", methods=["GET", "POST"])
def musteri_giris():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with connect() as db:
            customer = db.execute(
                "SELECT * FROM customers WHERE username=?",
                (username,)
            ).fetchone()

        if customer and check_password_hash(customer["password_hash"], password):
            if customer["expires"] >= datetime.now().strftime("%Y-%m-%d"):
                link = url_for("playlist", token=customer["token"], _external=True)
                return (
                    "<h2>Giriş uğurludur</h2>"
                    f"<a href='{escape(link)}'>M3U Playlist</a>"
                )

        return "Login və ya parol yanlışdır, yaxud abunəlik bitib."

    return """
    <h2>Müştəri girişi</h2>
    <form method="post">
    <input name="username" placeholder="Login" required>
    <input name="password" type="password" placeholder="Parol" required>
    <button>Daxil ol</button>
    </form>
    """


@app.route("/playlist/<token>")
def playlist(token):
    with connect() as db:
        customer = db.execute(
            "SELECT * FROM customers WHERE token=?", (token,)
        ).fetchone()
        channels = db.execute("SELECT * FROM channels").fetchall()

    if not customer:
        return "Müştəri tapılmadı", 404

    if customer["expires"] < datetime.now().strftime("%Y-%m-%d"):
        return "Abunəlik müddəti bitib", 403

    content = "#EXTM3U\n"

    for c in channels:
        content += f"#EXTINF:-1,{c['name']}\n{c['url']}\n"


    return Response(
        content,
        mimetype="application/vnd.apple.mpegurl",
        headers={"Content-Disposition": "inline; filename=playlist.m3u"}
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )


