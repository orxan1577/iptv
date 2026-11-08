import os
from flask import Flask, request, redirect, session
from markupsafe import escape
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-demo-key")

ADMIN_USER = "orxan"
ADMIN_PASS = "Orxan2026!"

channels = []
customers = []

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
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

    html = """
    <h1>ORXAN IPTV PANEL</h1>
    <a href="/logout">Çıxış</a>
    <hr>
    <h2>Kanal əlavə et</h2>
    <form action="/kanal" method="post">
    <input name="name" placeholder="Kanal adı">
    <input name="url" placeholder="Rəsmi yayım səhifəsi">
    <button>Əlavə et</button>
    </form>
    <h3>Kanallar</h3>
    """

    for i, c in enumerate(channels):
        html += f"<p>{escape(c['name'])} <a href='/izle/{i}'>CANLI İZLƏ</a> <a href='/kanal-sil/{i}'>Sil</a></p>"

    html += """
    <hr>
    <h2>Müştəri yarat</h2>
    <form action="/musteri" method="post">
    <input name="name" placeholder="Müştəri adı" required>
    <input name="username" placeholder="Login" required>
    <input name="password" placeholder="Parol" required>
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
        html += f"<p>Ad: {escape(c['name'])}<br>Login: {escape(c['username'])}<br>Bitmə tarixi: {escape(c['expires'])}</p><hr>"

    return html

@app.route("/kanal", methods=["POST"])
def kanal():
    if not session.get("login"):
        return redirect("/login")
    channels.append({"name": request.form["name"], "url": request.form["url"]})
    return redirect("/")

@app.route("/izle/<int:i>")
def izle(i):
    if not session.get("login"):
        return redirect("/login")
    if i < len(channels):
        c = channels[i]
        return f"<h2>{escape(c['name'])}</h2><iframe src='{escape(c['url'])}' width='100%' height='400'></iframe><p><a href='/'>Geri</a></p>"
    return "Kanal tapılmadı"

@app.route("/kanal-sil/<int:i>")
def kanal_sil(i):
    if not session.get("login"):
        return redirect("/login")
    if i < len(channels):
        channels.pop(i)
    return redirect("/")

@app.route("/musteri", methods=["POST"])
def musteri():
    if not session.get("login"):
        return redirect("/login")
    username = request.form["username"].strip()
    if any(c["username"] == username for c in customers):
        return "Bu login artıq mövcuddur."
    days = int(request.form["days"])
    expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    customers.append({
        "name": request.form["name"],
        "username": username,
        "password": request.form["password"],
        "expires": expires
    })
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


