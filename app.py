
import os
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote
from flask import Flask, request, redirect, Response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import escape

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL
        )
        """)
        db.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            expires TEXT NOT NULL,
            token TEXT UNIQUE
        )
        """)


def valid_customer(username, password):
    with connect() as db:
        c = db.execute(
            "SELECT * FROM customers WHERE username=?",
            (username,)
        ).fetchone()

    if not c:
        return None

    if c["expires"] < datetime.now().strftime("%Y-%m-%d"):
        return None

    if not check_password_hash(c["password_hash"], password):
        return None

    return c


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (request.form.get("username") == ADMIN_USER
                and request.form.get("password") == ADMIN_PASS):
            from flask import session
            session["admin"] = True
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
    from flask import session
    if not session.get("admin"):
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
    <input name="url" placeholder="İcazəli yayım linki" required>
    <button>Əlavə et</button>
    </form>
    <h3>Kanallar</h3>
    """

    for c in channels:
        html += (
            f"<p>{escape(c['name'])} "
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
        html += (
            f"<p>Ad: {escape(c['name'])}<br>"
            f"Login: {escape(c['username'])}<br>"
            f"Bitmə: {escape(c['expires'])}<br>"
            f"Server: https://iptv-kxu7.onrender.com<br>"
            f"Televizo: Xtream Codes API</p><hr>"
        )

    return html


@app.route("/kanal", methods=["POST"])
def kanal():
    from flask import session
    if not session.get("admin"):
        return redirect("/login")

    with connect() as db:
        db.execute(
            "INSERT INTO channels (name, url) VALUES (?, ?)",
            (request.form["name"], request.form["url"])
        )
    return redirect("/")


@app.route("/kanal-sil/<int:i>")
def kanal_sil(i):
    from flask import session
    if not session.get("admin"):
        return redirect("/login")

    with connect() as db:
        db.execute("DELETE FROM channels WHERE id=?", (i,))
    return redirect("/")


@app.route("/musteri", methods=["POST"])
def musteri():
    from flask import session
    if not session.get("admin"):
        return redirect("/login")

    username = request.form["username"].strip()
    password_hash = generate_password_hash(request.form["password"])
    days = int(request.form["days"])
    expires = (
        datetime.now() + timedelta(days=days)
    ).strftime("%Y-%m-%d")

    try:
        with connect() as db:
            db.execute(
                """INSERT INTO customers
                (name, username, password_hash, expires)
                VALUES (?, ?, ?, ?)""",
                (
                    request.form["name"],
                    username,
                    password_hash,
                    expires
                )
            )
    except sqlite3.IntegrityError:
        return "Bu login artıq mövcuddur."

    return redirect("/")


@app.route("/player_api.php")
def player_api():
    username = request.args.get("username", "")
    password = request.args.get("password", "")
    customer = valid_customer(username, password)

    if not customer:
        return jsonify({"user_info": {"auth": 0}}), 401

    action = request.args.get("action")

    if action == "get_live_categories":
        return jsonify([{
            "category_id": "1",
            "category_name": "Live TV",
            "parent_id": 0
        }])

    if action == "get_live_streams":
        with connect() as db:
            channels = db.execute(
                "SELECT * FROM channels"
            ).fetchall()

        return jsonify([{
            "num": i + 1,
            "name": c["name"],
            "stream_type": "live",
            "stream_id": c["id"],
            "stream_icon": "",
            "epg_channel_id": "",
           "category_id": 1,
            "container_extension": "m3u8"
        } for i, c in enumerate(channels)])

    expires = int(datetime.strptime(
        customer["expires"], "%Y-%m-%d"
    ).timestamp())

    return jsonify({
        "user_info": {
            "username": username,
            "password": password,
            "message": "Welcome",
            "auth": 1,
            "status": "Active",
            "exp_date": str(expires),
            "is_trial": "0",
            "active_cons": "0",
            "max_connections": "1",
            "allowed_output_formats": ["m3u8", "ts"]
        },
        "server_info": {
            "url": request.host,
            "port": "443" if request.is_secure else "80",
            "https_port": "443",
            "server_protocol": "https",
            "timezone": "Asia/Baku"
        }
    })


@app.route("/live/<username>/<password>/<int:channel_id>.<ext>")
def live(username, password, channel_id, ext):
    if not valid_customer(username, password):
        return "Giriş məlumatları yanlışdır", 401

    with connect() as db:
        channel = db.execute(
            "SELECT * FROM channels WHERE id=?",
            (channel_id,)
        ).fetchone()

    if not channel:
        return "Kanal tapılmadı", 404

    url = channel["url"]
    if not url.startswith(("https://", "http://")):
        return "Yanlış yayım ünvanı", 400

    return redirect(url, code=302)


@app.route("/get.php")
def get_playlist():
    username = request.args.get("username", "")
    password = request.args.get("password", "")

    if not valid_customer(username, password):
        return "Giriş məlumatları yanlışdır", 401

    with connect() as db:
        channels = db.execute("SELECT * FROM channels").fetchall()

    content = "#EXTM3U\n"
    for c in channels:
        stream = (
            f"/live/{quote(username)}/{quote(password)}/"
            f"{c['id']}.m3u8"
        )
        content += f"#EXTINF:-1,{c['name']}\n"
        content += request.host_url.rstrip("/") + stream + "\n"

    return Response(content, mimetype="application/vnd.apple.mpegurl")


@app.route("/logout")
def logout():
    from flask import session
    session.clear()
    return redirect("/login")


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )

