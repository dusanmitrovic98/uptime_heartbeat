import eventlet
eventlet.monkey_patch()

import threading
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
# from flask_session import Session
from threading import Thread
import time
import requests
import json
import os
from flask_socketio import SocketIO, emit
from database import db  # <-- Import the database layer
import asyncio  # <-- For running async DB calls

app = Flask(__name__)

# app.config['SESSION_TYPE'] = 'filesystem'
# Session(app)
# Use Flask's default session for Windows compatibility
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
# Use eventlet mode for SocketIO for production and real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

DATA_FILE = "data.json"
PING_HISTORY_FILE = "ping_history.json"
DATA_LOCK = threading.Lock()

last_ping = {}

# --- Asyncio event loop for DB ---
# Start a background event loop for async DB calls from sync Flask routes
asyncio_loop = asyncio.new_event_loop()
def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()
threading.Thread(target=start_loop, args=(asyncio_loop,), daemon=True).start()

# --- Data helpers ---
def load_data():
    # Load all URLs from MongoDB using background event loop
    future = asyncio.run_coroutine_threadsafe(db.find("urls"), asyncio_loop)
    return future.result()

def save_data(data):
    # Replace all documents in 'urls' collection with new data using background event loop
    future = asyncio.run_coroutine_threadsafe(db.replace_all("urls", data), asyncio_loop)
    future.result()

def load_ping_history():
    with DATA_LOCK:
        if not os.path.exists(PING_HISTORY_FILE):
            return {}
        try:
            with open(PING_HISTORY_FILE, "r") as f:
                history = json.load(f)
                # Clean up: only keep dicts with 'ts' and 'ok', and last 20
                for url in history:
                    history[url] = [p for p in history[url] if isinstance(p, dict) and 'ts' in p and 'ok' in p][-20:]
                return history
        except Exception:
            return {}

def save_ping_history(history):
    with DATA_LOCK:
        # Clean up before saving, keep only last 20
        for url in history:
            history[url] = [p for p in history[url] if isinstance(p, dict) and 'ts' in p and 'ok' in p][-20:]
        with open(PING_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

# --- Pinger thread ---
def ping_loop():
    global last_ping
    while True:
        data = load_data()
        now = time.time()
        history = load_ping_history()
        for entry in data:
            url = entry["url"]
            interval = entry.get("interval", 60)
            # Only ping if enough time has passed since last ping
            if now - last_ping.get(url, 0) >= interval:
                last_ping[url] = now  # Update BEFORE ping to prevent double pings
                ping_success = True
                try:
                    r = requests.get(url, timeout=10)
                    print(f"Pinged {url}: {r.status_code}")
                    ping_success = (r.status_code == 200)
                except Exception as e:
                    print(f"Ping failed for {url}: {e}")
                    ping_success = False
                # Save ping time and result
                if url not in history:
                    history[url] = []
                history[url].append({"ts": int(now), "ok": ping_success})
                # Keep only last 20
                history[url] = history[url][-20:]
                save_ping_history(history)
                # Emit pinged event to frontend
                socketio.emit('pinged', {'url': url, 'ok': ping_success})
        time.sleep(1)

@app.route("/")
def index():
    # Clear ping history on website refresh
    save_ping_history({})
    return render_template("index.html")

@app.route("/api/urls", methods=["GET", "POST", "DELETE"])
def urls():
    try:
        data = load_data()
    except Exception as e:
        return jsonify(success=False, error="Failed to load URLs: {}".format(str(e))), 500
    if request.method == "POST":
        try:
            new_url = request.json.get("url")
            interval = int(request.json.get("interval", 60))
            found = False
            for d in data:
                if d["url"] == new_url:
                    d["interval"] = interval
                    found = True
                    break
            if not found and new_url:
                data.append({"url": new_url, "interval": interval})
            save_data(data)
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error="Failed to add URL: {}".format(str(e))), 500

    elif request.method == "DELETE":
        try:
            url_to_remove = request.json.get("url")
            data = [d for d in data if d["url"] != url_to_remove]
            save_data(data)
            # Remove ping history for deleted url
            history = load_ping_history()
            if url_to_remove in history:
                del history[url_to_remove]
                save_ping_history(history)
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error="Failed to delete URL: {}".format(str(e))), 500

    return jsonify(data)

@app.route("/api/ping_history", methods=["GET"])
def ping_history():
    history = load_ping_history()
    return jsonify(history)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route("/login", methods=["GET", "POST"])
def login():
    from dotenv import load_dotenv
    load_dotenv()
    error = None
    if request.method == "POST":
        secret_key = request.form.get("secret_key")
        expected = os.getenv("SECRET_KEY")
        if secret_key == expected:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error = "Invalid secret key."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
@app.before_request
def require_login():
    if request.endpoint not in ("login", "static_files") and not session.get("logged_in"):
        return redirect(url_for("login"))

@app.route("/export_data")
def export_data():
    return send_from_directory('.', DATA_FILE, as_attachment=True)

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    # 1. Check for --port argument
    port = None
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
            except ValueError:
                pass
    # 2. If not set, try .env
    if port is None:
        load_dotenv()
        port_env = os.getenv("PORT")
        if port_env:
            try:
                port = int(port_env)
            except ValueError:
                port = None
    # 3. Default to 5000
    if port is None:
        port = 5000
    # Always start the ping thread (no reloader)
    Thread(target=ping_loop, daemon=True).start()
    socketio.run(app, debug=True, use_reloader=False, host="0.0.0.0", port=port)
