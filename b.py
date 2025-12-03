import os
import sqlite3
import random
from datetime import datetime, date, timedelta
import requests
import io
import base64
import matplotlib.pyplot as plt
from flask import Flask, request, session, g, redirect, url_for, render_template_string, Response
from flask_bcrypt import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def get_db_connection():
    # store DB in same folder as final.py
    db_path = os.path.join(os.path.dirname(os.path.abspath(_file_)), "mental_health.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------
# CONFIG
# -----------------------
# -----------------------
# DATABASE
# -----------------------

import sqlite3
from flask import Flask, g, session

app = Flask(__name__)
app.secret_key = "your_secret_key"
API_KEY = "ZTboeBJE60P0IaAUpmSP2A"  # Replace if needed
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)

DB_FILE = "daily_checkup.db"

API_KEY = "ZTboeBJE60P0IaAUpmSP2A"  # Replace if needed
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)

@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=?", (session["user_id"],))
        g.user = cur.fetchone()
        conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Users table with is_admin
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age INTEGER,
        username TEXT UNIQUE,
        password_hash TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)

    # Daily checkup table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_checkup_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        created_at TEXT,
        mental_score REAL,
        stress_score REAL,
        burnout_score REAL
    )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def init_feedback_table():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedbacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    conn.commit()
    conn.close()
    print("Feedback table initialized successfully!")

def create_default_admin():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE username='admin'")
    admin = cur.fetchone()

    if not admin:
        from flask_bcrypt import Bcrypt
        bcrypt = Bcrypt(app)
        pw_hash = bcrypt.generate_password_hash("admin123").decode()

        cur.execute("""
            INSERT INTO users (name, age, username, password_hash, is_admin)
            VALUES (?, ?, ?, ?, ?)
        """, ("Administrator", 0, "admin", pw_hash, 1))

        conn.commit()
        print("Admin created: username='admin', password='admin123'")

    conn.close()

# Run once at startup
init_db()
init_feedback_table()
create_default_admin()

@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=?", (session["user_id"],))
        g.user = cur.fetchone()
        conn.close()

music_links = [
    "https://www.youtube.com/watch?v=2OEL4P1Rz04",
    "https://www.youtube.com/watch?v=1ZYbU82GVz4"
]


def fetch_quote():
    try:
        r = requests.get("https://api.api-ninjas.com/v1/quotes?category=happiness",
                         headers={"X-Api-Key": API_KEY}, timeout=5)
        if r.status_code == 200:
            return r.json()[0]["quote"]
    except:
        pass
    return "Stay positive, stay strong."


def fetch_routine_tips():
    defaults = ["Sleep 7-8 hours", "Exercise 30 mins", "Take regular breaks", "Practice deep breathing"]
    return defaults


def fetch_music_links():
    return random.sample(music_links, min(2, len(music_links)))


def analyze_mental_state(scores, qtype):
    """Return (analysis_text, list_of_tips) based on numeric scores list"""
    avg_score = sum(scores) / len(scores)
    analysis = ""
    precautions = []

    if qtype == "daily":
        if avg_score >= 3.5:
            analysis = "You seem to be experiencing a high level of low mood or distress recently."
            precautions = [
                "Talk to someone you trust about how you feel.",
                "Seek professional help if symptoms persist.",
                "Make small daily goals and maintain routine."
            ]
        elif avg_score >= 2.5:
            analysis = "You may be feeling moderately low or stressed; some small changes can help."
            precautions = [
                "Improve sleep routine and include light exercise.",
                "Practice short mindfulness or breathing sessions.",
                "Limit caffeine and screen time before bed."
            ]
        else:
            analysis = "Your daily checkup indicates relatively good mood and balance."
            precautions = [
                "Keep your positive habits and social connections.",
                "Continue regular exercise and restful sleep.",
                "Maintain mindfulness practices to stay balanced."
            ]
    else:  # stress
        if avg_score >= 3.5:
            analysis = "Your stress levels are high — immediate steps to reduce load are recommended."
            precautions = [
                "Prioritize tasks and practice time management.",
                "Use breathing exercises and short breaks often.",
                "Consider speaking with a counselor or mentor."
            ]
        elif avg_score >= 2.5:
            analysis = "Your stress is moderate — try regular relaxation and reduce overload."
            precautions = [
                "Incorporate breaks and calming music.",
                "Keep reasonable work hours and sleep well.",
                "Journal or talk about worries to reduce build-up."
            ]
        else:
            analysis = "You handle stress well currently. Keep doing what works for you."
            precautions = [
                "Continue your coping strategies and regular sleep.",
                "Engage in social activities and light exercise."
            ]

    return analysis, precautions


def fetch_fixed_questions(qtype="daily"):
    options = [
        {"text": "Never (1)", "score": 1},
        {"text": "Sometimes (2)", "score": 2},
        {"text": "Often (3)", "score": 3},
        {"text": "Always (4)", "score": 4},
    ]

    if qtype == "daily":
        questions = [{"id": f"{qtype}_{i}", "text": q, "options": options} for i, q in enumerate(questions_daily)]
    else:
        questions = [{"id": f"{qtype}_{i}", "text": q, "options": options} for i, q in enumerate(questions_stress)]

    return questions


# -----------------------
# AUTH ROUTES
# -----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        age = request.form["age"]
        username = request.form["username"]
        password = request.form["password"]

        pw_hash = generate_password_hash(password).decode("utf-8")
        
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name, age, username, password_hash) VALUES (?, ?, ?, ?)",
                (name, age, username, pw_hash)
            )
            conn.commit()
        except Exception as e:
            conn.close()
            return f"<h3>Error: {e}</h3>"
        conn.close()
        return redirect(url_for("login"))

    html = """
<style>
  body {margin:0;height:100vh;display:flex;justify-content:center;align-items:center;background-color:#f1f4f9;font-family:Arial,sans-serif;}
  .register-box {background:white;padding:30px 40px;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,0.1);text-align:center;max-width:400px;width:100%;}
  input {width:100%;padding:8px 10px;margin:8px 0;border-radius:6px;border:1px solid #ccc;font-size:14px;box-sizing:border-box;}
  button {width:100%;background:#4a6cf7;color:white;font-size:16px;border:none;border-radius:8px;padding:12px;cursor:pointer;margin-top:10px;}
  h2 {margin-bottom:20px;color:#233;}
</style>
<div class="register-box">
  <h2>Register</h2>
  <form method="post">
    Name:<input name="name" required><br>
    Age:<input name="age" type="number" min="1" required><br>
    Username:<input name="username" required><br>
    Password:<input name="password" type="password" required><br><br>
    <button type="submit">Register</button>
  </form>
</div>
"""
    return render_template_string(html)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
        return "<h3>Invalid credentials ❌</h3>"

    html = """
<style>
  body {margin:0;height:100vh;display:flex;justify-content:center;align-items:center;background-color:#f1f4f9;font-family:Arial,sans-serif;}
  .login-box {background:white;padding:30px 40px;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,0.1);text-align:center;max-width:350px;width:100%;}
  input {width:100%;padding:8px 10px;margin:8px 0;border-radius:6px;border:1px solid #ccc;font-size:14px;box-sizing:border-box;}
  button {width:100%;background:#4a6cf7;color:white;font-size:16px;border:none;border-radius:8px;padding:12px;cursor:pointer;margin-top:10px;}
  h2 {margin-bottom:20px;color:#233;}
  p a {color:#4a6cf7;text-decoration:none;font-weight:600;}
</style>
<div class="login-box">
  <h2>Login 🔐</h2>
  <form method="post">
    Username: <input name="username" required><br>
    Password: <input name="password" type="password" required><br><br>
    <button type="submit">Login</button>
  </form>
  <p>No account? Register here <a href="/register">Register</a></p>
</div>
"""
    return render_template_string(html)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    if not g.user:
        return redirect("/login")  # Ensure user is logged in

    # GET request: show feedback form
    if request.method == "GET":
        html = """
        <style>
            body {background:#eef4ff;font-family:Arial,sans-serif;}
            .box {width:90%;max-width:450px;background:white;padding:25px;margin:80px auto;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.15);text-align:center;}
            textarea {width:100%;height:120px;padding:10px;border-radius:8px;border:1px solid #ccc;font-size:15px;margin-top:10px;}
            .star-container {direction:rtl;unicode-bidi:bidi-override;font-size:28px;margin-bottom:10px;}
            .star-container input {display:none;}
            .star-container label {color:#ccc;cursor:pointer;}
            .star-container input:checked ~ label,
            .star-container label:hover,
            .star-container label:hover ~ label {color:gold;}
            .btn {margin-top:15px;background:#007bff;color:white;padding:10px 18px;border:none;border-radius:8px;font-size:16px;cursor:pointer;width:100%;}
            .btn:hover {background:#005fcc;}
            .skip-btn {background:#888;margin-top:10px;}
            .skip-btn:hover {background:#555;}
        </style>

        <div class="box">
            <h2>We value your feedback</h2>
            <p>Please share your experience before logging out.</p>

            <form method="POST">
                <div class="star-container">
                    <input type="radio" name="rating" id="star5" value="5"><label for="star5">★</label>
                    <input type="radio" name="rating" id="star4" value="4"><label for="star4">★</label>
                    <input type="radio" name="rating" id="star3" value="3"><label for="star3">★</label>
                    <input type="radio" name="rating" id="star2" value="2"><label for="star2">★</label>
                    <input type="radio" name="rating" id="star1" value="1"><label for="star1">★</label>
                </div>

                <textarea name="feedback" placeholder="Write your feedback here..."></textarea>

                <button type="submit" name="submit" value="1" class="btn">Submit</button>
                <button type="submit" name="skip" value="1" class="btn skip-btn">Skip & Logout</button>
            </form>
        </div>
        """
        return render_template_string(html)

    # POST request
    if "skip" in request.form:
        session.clear()
        return redirect(url_for("login"))

    if "submit" in request.form:
        feedback_text = request.form.get("feedback", "").strip()
        rating = request.form.get("rating", None)

        # Save feedback if any message or rating is provided
        if feedback_text or rating:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO feedbacks (user_id, message, created_at) VALUES (?, ?, datetime('now'))",
                (g.user["id"], f"Rating: {rating or 'N/A'} | {feedback_text}")
            )
            conn.commit()
            conn.close()

        # Show thank you page
        html = """
        <style>
            body {background:#eef4ff;font-family:Arial,sans-serif;}
            .box {width:90%;max-width:450px;background:white;padding:25px;margin:80px auto;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.15);text-align:center;}
            .btn {margin-top:15px;background:#007bff;color:white;padding:10px 18px;border:none;border-radius:8px;font-size:16px;cursor:pointer;width:100%;}
            .btn:hover {background:#005fcc;}
        </style>

        <div class="box">
            <h2>Thank you!</h2>
            <p>Your feedback helps us improve and support you better.</p>

            <form method="POST" action="/final_logout">
                <button type="submit" class="btn">Logout</button>
            </form>
        </div>
        """
        return render_template_string(html)

@app.route("/final_logout", methods=["POST"])
def final_logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    if not g.user:
        return redirect(url_for("login"))

    quote = fetch_quote()  # English-only

    html = """
    <style>
      body {
        background: linear-gradient(135deg, #9be7ff 0%, #67d1fb 100%);
        font-family: Arial, sans-serif;
        color: #003c6f;
        margin: 0;
      }
      .menu-btn {
        position: fixed;
        top: 20px;
        left: 20px;
        width: 40px;
        height: 32px;
        background: rgba(255,255,255,0.7);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 9999;
        backdrop-filter: blur(4px);
      }
      .menu-btn span {
        display: block;
        width: 24px;
        height: 3px;
        background: #003c6f;
        margin: 4px 0;
        border-radius: 3px;
        transition: 0.3s;
      }
      .side-menu {
        position: fixed;
        top: 0;
        left: -270px;
        width: 260px;
        height: 100%;
        background: rgba(255,255,255,0);
        backdrop-filter: blur(10px);
        padding: 20px;
        overflow-y: auto;
        transition: 0.4s;
        z-index: 9998;
        opacity: 0;
      }
      .side-menu.open {
        left: 0;
        opacity: 1;
        background: rgba(255,255,255,0.25);
      }
      .side-menu a {
        display: block;
        padding: 12px;
        font-size: 18px;
        border-radius: 8px;
        margin-bottom: 8px;
        color: #004a99;
        text-decoration: none;
        backdrop-filter: blur(5px);
        background: rgba(255,255,255,0.3);
      }
      .side-menu a:hover {
        background: rgba(255,255,255,0.5);
      }
      .center-content {
        max-width: 600px;
        margin: 80px auto 60px;
        padding: 40px;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(8px);
        border-radius: 18px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        text-align: center;
        color: #003c6f;
      }
      .center-content h1 {
        font-size: 2.8rem;
        margin-bottom: 15px;
        font-weight: 700;
      }
      .center-content p {
        margin: 15px 0;
        font-style: italic;
      }
      .center-content .emergency {
        font-weight: 700;
        color: #d32f2f;
        margin-top: 25px;
      }
      .center-content img {
        max-width: 100%;
        margin-top: 30px;
        border-radius: 12px;
      }
    </style>

    <div class="menu-btn" onclick="toggleMenu()" aria-label="Open menu" role="button">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <div id="sideMenu" class="side-menu" aria-hidden="true">
      <h2>Menu</h2>
      <a href="/daily_checkup">📝 Start Daily Checkup</a>
      <a href="/routine">🗓 Routine Tips</a>
      <a href="/breathing">💨 Breathing Exercise</a>
      <a href="/music_suggestions">🎵 Stress Relief Music</a>
      <a href="/history">📜 Your History</a>
      <a href="/graph">📊 View Graph</a>
      <a href="/daily_report">📄 Daily Report</a>
      <a href="/monthly_report">📄 Monthly Report</a>
      <a href="/games">🎮 Games</a>
      <a href="/logout">🚪 Logout</a>
      <a href="/view_feedback">Admin Panel</a>
    </div>

    <script>
    function toggleMenu() {
      var m = document.getElementById("sideMenu");
      m.classList.toggle("open");
      m.setAttribute("aria-hidden", !m.classList.contains("open"));
    }
    </script>

    <div class="center-content" role="main">
      <h1>Welcome, {{ user['name'] }} 👋</h1>
      <p><i>{{ quote }}</i></p>
      <p class="emergency">
        Emergency Helpline: 
        <a href="tel:104" style="color:#d32f2f;">📞 104</a>
      </p>
    </div>
    """

    return render_template_string(html, user=g.user, quote=quote)


@app.route("/view_feedback")
def view_feedback():
    # Correct admin check
    if not g.user or g.user["is_admin"] != 1:
        return "Access Denied", 403

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.id, u.name, f.message, f.created_at
        FROM feedbacks f
        LEFT JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """)
    feedbacks = cur.fetchall()
    conn.close()

    return render_template_string("""
    <html>
    <head>
        <title>Feedbacks</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; max-width:900px; margin:auto; background:#f4f4f4; }
            h2 { color:#1b4b8a; }
            .feedback-card { background:white; padding:16px; border-radius:8px; margin-bottom:14px; box-shadow:0 2px 6px rgba(0,0,0,0.1);}
            .time { font-size:0.9rem; color:gray; }
        </style>
    </head>
    <body>
        <h2>📨 User Feedbacks</h2>
        {% for f in feedbacks %}
        <div class="feedback-card">
            <p><b>User:</b> {{ f['name'] or 'Anonymous' }}</p>
            <p>{{ f['message'] }}</p>
            <p class="time">{{ f['created_at'] }}</p>
        </div>
        {% endfor %}
        <p><a href="/">🏠 Back to Home</a></p>
    </body>
    </html>
    """, feedbacks=feedbacks)

# app.py
import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib

# ---------- CONFIG ----------
APP_SECRET = "replace-with-a-secret"
DB_FILE = "daily_checkup.db"
MODEL_FILE = "daily_checkup_model.joblib"


# ---------- 10 FIXED QUESTIONS (English only) ----------
QUESTIONS = [
    "Q1 - How often have you felt anxious in the last week? (0 = Not at all, 10 = Extremely)",
    "Q2 - How often have you felt stressed in the last week? (0 = Not at all, 10 = Extremely)",
    "Q3 - How well have you slept recently? (0 = Very poor, 10 = Excellent)",
    "Q4 - How energetic have you felt daily? (0 = None, 10 = Very energetic)",
    "Q5 - How often have you felt overwhelmed by work / responsibilities? (0 = Never, 10 = Always)",
    "Q6 - How often have you felt irritable or easily angered? (0 = Never, 10 = Always)",
    "Q7 - How much difficulty have you faced concentrating? (0 = None, 10 = Severe)",
    "Q8 - How often have you felt hopeless or sad? (0 = Never, 10 = Always)",
    "Q9 - How satisfied are you with your social interactions/support? (0 = Not at all, 10 = Very satisfied)",
    "Q10 - How motivated are you to perform daily tasks? (0 = Not at all, 10 = Very motivated)"
]

def train_and_save_model(path=MODEL_FILE, n_samples=1200):
    """
    Train a realistic synthetic model (mimics real correlations) and save scaler+model.
    This runs only the first time if no MODEL_FILE exists.
    """
    rng = np.random.default_rng(12345)
    # Generate synthetic but realistic data (values 0..10)
    data = {}
    for i in range(1, 11):
        data[f"Q{i}"] = rng.integers(0, 11, size=n_samples)

    df = pd.DataFrame(data)

    # realistic correlations:
    # - mental_score increases with good sleep (Q3), energy (Q4), social satisfaction (Q9), motivation (Q10)
    # - mental_score decreases with anxiety (Q1), stress (Q2), hopelessness (Q8), concentration difficulties (Q7)
    df["mental_score"] = (
        0.25 * df["Q3"] + 0.20 * df["Q4"] + 0.15 * df["Q9"] + 0.10 * df["Q10"]
        - 0.18 * df["Q1"] - 0.12 * df["Q2"] - 0.10 * df["Q8"] - 0.10 * df["Q7"]
        + rng.normal(0, 0.6, size=n_samples)
    )
    # clamp 0..10
    df["mental_score"] = df["mental_score"].clip(0, 10)

    # stress_score increases with Q1,Q2,Q5,Q6 and reduces with good sleep/energy
    df["stress_score"] = (
        0.30 * df["Q1"] + 0.30 * df["Q2"] + 0.20 * df["Q5"] + 0.10 * df["Q6"]
        - 0.10 * df["Q3"] - 0.05 * df["Q4"]
        + rng.normal(0, 0.6, size=n_samples)
    )
    df["stress_score"] = df["stress_score"].clip(0, 10)

    # burnout: combination of sustained stress + low mental health
    df["burnout"] = (
        0.6 * df["stress_score"] + 0.4 * (10 - df["mental_score"])
        + rng.normal(0, 0.4, size=n_samples)
    )
    df["burnout"] = df["burnout"].clip(0, 10)

    X = df[[f"Q{i}" for i in range(1, 11)]].values
    y = df[["mental_score", "stress_score", "burnout"]].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = RandomForestRegressor(n_estimators=200, random_state=42)
    model.fit(X_scaled, y)

    # Save both scaler and model together
    joblib.dump({"scaler": scaler, "model": model}, path)
    return scaler, model

def load_model(path=MODEL_FILE):
    data = joblib.load(path)
    return data["scaler"], data["model"]

if not os.path.exists(MODEL_FILE):
    scaler, model = train_and_save_model(MODEL_FILE, n_samples=1500)
else:
    scaler, model = load_model(MODEL_FILE)

# ---------- UTILITY: derive causes & precautions ----------
def derive_causes_precautions(answers, mental_score, stress_score, burnout_score):
    """
    answers: list/length 10 numeric (0..10)
    returns (causes list, precautions list)
    We'll derive causes using simple interpretable rules based on important questions.
    """
    causes = []
    precautions = []

    Q = {i+1: answers[i] for i in range(10)}

    # Mental-related checks
    if mental_score < 4:
        causes.append("Low overall mood — likely due to high anxiety, poor sleep or low social support.")
        precautions.append("Consider reaching out to a mental health professional and practicing regular sleep hygiene.")
    elif mental_score < 7:
        causes.append("Mild to moderate dip in mood — may be caused by stress, low motivation or lack of restful sleep.")
        precautions.append("Establish a daily routine, include short exercise, and try mindfulness/breathing exercises.")
    else:
        causes.append("Good mental health indicators overall.")
        precautions.append("Keep maintaining your healthy habits and social connections.")

    # Check specific contributing factors (rules informed by question meanings)
    if Q[1] >= 7 or Q[2] >= 7:
        causes.append("High anxiety or frequent stress reported (questions about anxiety/stress).")
        precautions.append("Practice stress-management: short breathing breaks, schedule tasks, consider counseling.")

    if Q[3] <= 4:
        causes.append("Poor sleep quality.")
        precautions.append("Improve sleep hygiene: consistent bedtime, reduce screens before sleep, avoid caffeine late.")

    if Q[5] >= 7 or Q[6] >= 7:
        causes.append("High workload/irritability — signs of overload.")
        precautions.append("Prioritize tasks, set boundaries, ask for help or delegate when possible.")

    if Q[7] >= 7 or Q[8] >= 7:
        causes.append("Difficulty concentrating and/or frequent hopeless feelings.")
        precautions.append("Break tasks into small steps, journal your thoughts, and reach out if symptoms persist.")

    if Q[9] <= 4:
        causes.append("Low social support or dissatisfaction with social interactions.")
        precautions.append("Try reconnecting with supportive friends/family and join small group activities.")

    if burnout_score >= 7:
        causes.append("High burnout risk (sustained stress & low mental resilience).")
        precautions.append("Take immediate rest, reduce commitments, consider professional support.")

    # Deduplicate tips and causes, keep order
    causes = list(dict.fromkeys(causes))
    precautions = list(dict.fromkeys(precautions))
    return causes, precautions

# ---------- ROUTE: Daily Checkup (single form) ----------
# ---------- ROUTE: Daily Checkup (single form, one question at a time) ----------
@app.route("/daily_checkup", methods=["GET", "POST"])
def daily_checkup():
    if request.method == "GET":
        return render_template_string("""
        <!doctype html>
        <html>
        <head>
          <title>Daily Checkup</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              background: #f0f4f8;
              display: flex;
              justify-content: center;
              align-items: center;
              min-height: 100vh;
              margin: 0;
            }
            .card {
              background: white;
              padding: 30px;
              border-radius: 12px;
              box-shadow: 0 6px 20px rgba(0,0,0,0.1);
              width: 400px;
            }
            h2 { color: #1b4b8a; text-align: center; }
            label { font-weight: bold; display: block; margin-bottom: 8px; }
            input[type=number] {
              width: 100%;
              padding: 8px;
              margin-bottom: 15px;
              border-radius: 6px;
              border: 1px solid #ccc;
            }
            button {
              padding: 10px 20px;
              background: #1b4b8a;
              color: white;
              border: none;
              border-radius: 8px;
              font-weight: bold;
              cursor: pointer;
              width: 100%;
            }
            .progress { text-align: center; margin-bottom: 15px; color:#1b4b8a; }
          </style>
          <script>
            const questions = {{ questions|tojson }};
            let answers = [];
            let index = 0;

            function showQuestion() {
              if(index >= questions.length){
                // Submit answers via POST
                let form = document.getElementById('checkupForm');
                answers.forEach((v,i) => {
                  let input = document.createElement('input');
                  input.type = 'hidden';
                  input.name = 'Q'+(i+1);
                  input.value = v;
                  form.appendChild(input);
                });
                form.submit();
                return;
              }

              document.getElementById('questionLabel').innerText = questions[index];
              document.getElementById('numInput').value = '';
              document.getElementById('progress').innerText = 'Question ' + (index+1) + ' of ' + questions.length;
            }

            function nextQuestion(event){
              event.preventDefault();
              let val = parseFloat(document.getElementById('numInput').value);
              if(isNaN(val) || val < 0 || val > 10){
                alert('Please enter a value between 0 and 10');
                return;
              }
              answers.push(val);
              index++;
              showQuestion();
            }

            window.onload = showQuestion;
          </script>
        </head>
        <body>
          <div class="card">
            <h2>Daily Mental Health Checkup</h2>
            <div class="progress" id="progress"></div>
            <form id="checkupForm" method="post" onsubmit="nextQuestion(event)">
              <label id="questionLabel"></label>
              <input type="number" id="numInput" min="0" max="10" required>
              <button type="submit">Next</button>
            </form>
          </div>
        </body>
        </html>
        """, questions=QUESTIONS)

    # POST: collect answers (already sent as hidden inputs)
    answers = []
    for i in range(1, 11):
        val = request.form.get(f"Q{i}", "").strip()
        val = float(val) if val else 0.0
        if val < 0: val = 0.0
        if val > 10: val = 10.0
        answers.append(val)

    # Scale & predict
    X_in = scaler.transform([answers])
    pred = model.predict(X_in)[0]
    mental_score = float(np.clip(pred[0], 0.0, 10.0))
    stress_score = float(np.clip(pred[1], 0.0, 10.0))
    burnout_score = float(np.clip(pred[2], 0.0, 10.0))

    # Save to DB
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO daily_checkup_history (user_id, created_at, mental_score, stress_score, burnout_score)
        VALUES (?, ?, ?, ?, ?)
    """, (
        g.user['id'],  # logged-in user
        datetime.utcnow().isoformat(),
        mental_score,
        stress_score,
        burnout_score
      )),  
    conn.commit()
    conn.close()

    # Causes & precautions
    causes, precautions = derive_causes_precautions(answers, mental_score, stress_score, burnout_score)

    return render_template_string("""
    <!doctype html>
    <html>
    <head>
      <title>Daily Checkup - Results</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 20px; max-width:900px; margin:auto; background:#f0f4f8; }
        h2 { color:#1b4b8a; }
        .card { background:white; padding:20px; border-radius:10px; margin-bottom:15px; box-shadow:0 4px 15px rgba(0,0,0,0.08); }
        ul, ol { line-height:1.6; }
        .score { font-size:1.1rem; font-weight:700; color:#0b3d91; }
        .btn { display:inline-block; margin-top:10px; padding:10px 15px; background:#1b4b8a; color:white; border-radius:8px; text-decoration:none; font-weight:bold; }
      </style>
    </head>
    <body>
      <h2>✅ Daily Checkup Results</h2>

      <div class="card">
        <h3>All Answers</h3>
        <ol>
          {% for a in answers %}
            <li><b>{{questions[loop.index0]}}</b> → {{a}}</li>
          {% endfor %}
        </ol>
      </div>

      <div class="card">
        <h3>Predicted Scores</h3>
        <p class="score">Mental Health Score: {{ '%.2f'|format(mental) }} / 10</p>
        <p class="score">Stress Score: {{ '%.2f'|format(stress) }} / 10</p>
        <p class="score">Burnout Risk: {{ '%.2f'|format(burnout) }} / 10</p>
      </div>

      <div class="card">
        <h3>Likely Causes</h3>
        <ul>
          {% for c in causes %}
            <li>{{c}}</li>
          {% endfor %}
        </ul>
      </div>

      <div class="card">
        <h3>Recommended Precautions</h3>
        <ul>
          {% for p in precautions %}
            <li>{{p}}</li>
          {% endfor %}
        </ul>
      </div>

      <a href="/" class="btn">🏠 Back to Home</a>
      <a href="{{ url_for('daily_checkup') }}" class="btn">📝 Retake Checkup</a>
    </body>
    </html>
    """, answers=answers, questions=QUESTIONS,
         mental=mental_score, stress=stress_score, burnout=burnout_score,
         causes=causes, precautions=precautions)

import random
import io
from flask import render_template_string, redirect, url_for, g

@app.route("/music_suggestions")
def music_suggestions():
    if not g.user:
        return redirect(url_for("login"))

    # Publicly available free melodies / ambient tracks
    tracks = [
        ("Peaceful Piano", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"),
        ("Relaxing Strings", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"),
        ("Calm Guitar", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"),
        ("Gentle Rain", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3"),
        ("Meditative Ocean", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3"),
        ("Soft Ambient", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3"),
        ("Soothing Piano", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3"),
        ("Nature Sounds", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3"),
        ("Relaxing Wind", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3"),
        ("Calm Evening", "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3"),
        # Add more tracks here up to 50+ if needed
    ]

    # Shuffle tracks so the playlist order changes every visit
    random.shuffle(tracks)

    dashboard_url = url_for("dashboard") if "dashboard" in [r.endpoint for r in app.url_map.iter_rules()] else "/"

    html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <title>🎶 Music Suggestions</title>
    <style>
      body {{
        font-family: 'Segoe UI', sans-serif;
        background-image: url('https://images.unsplash.com/photo-1507525428034-b723cf961d3e');
        background-size: cover;
        background-attachment: fixed;
        color: #fff;
        padding: 20px;
        text-align: center;
      }}
      h2 {{
        font-size: 28px;
        color: #fffbf0;
        text-shadow: 1px 1px 4px #000;
        margin-bottom: 12px;
      }}
      .song {{
        background: rgba(0,0,0,0.5);
        border-radius: 12px;
        padding: 12px;
        margin: 10px auto;
        width: 85%;
        max-width: 500px;
        box-shadow: 0 3px 8px rgba(0,0,0,0.3);
      }}
      audio {{
        width: 100%;
        margin-top: 8px;
      }}
      .menu {{
        margin-top: 25px;
      }}
      .menu a {{
        display:inline-block;
        background: #4a90e2;
        color:white;
        padding:10px 16px;
        border-radius:8px;
        margin:4px;
        text-decoration:none;
        font-weight:bold;
      }}
      .menu a:hover {{ background:#357ab7; }}
      #loadMore {{
        display:inline-block;
        background: #2e7d32;
        padding:10px 16px;
        margin:12px 0;
        border-radius:8px;
        color:white;
        cursor:pointer;
        font-weight:bold;
      }}
      #loadMore:hover {{ background:#1b4b18; }}
    </style>
    </head>
    <body>
      <h2>🎵 Relaxing & Melody Tracks</h2>
      <div id="playlist">
    """

    # Initially show 5 tracks
    for idx, (title, url) in enumerate(tracks[:5]):
        html += f"""
        <div class="song" data-index="{idx}">
          <h3>{title}</h3>
          <audio controls preload="none">
            <source src="{url}" type="audio/mpeg">
            Your browser does not support the audio element.
          </audio>
        </div>
        """

    html += """
      </div>
      <div id="loadMore">Load More Songs</div>
      <div class="menu">
        <a href="/">🏠 Back to Home</a>
      </div>

      <script>
        const tracks = """ + str(tracks) + """;
        let loaded = 5;
        const loadMoreBtn = document.getElementById('loadMore');
        loadMoreBtn.addEventListener('click', function() {
          const playlist = document.getElementById('playlist');
          let end = loaded + 5;
          for(let i=loaded; i<end && i<tracks.length; i++){
            const div = document.createElement('div');
            div.className = 'song';
            div.dataset.index = i;
            div.innerHTML = `<h3>${tracks[i][0]}</h3>
                             <audio controls preload="none">
                               <source src="${tracks[i][1]}" type="audio/mpeg">
                               Your browser does not support the audio element.
                             </audio>`;
            playlist.appendChild(div);
          }
          loaded += 5;
          if(loaded >= tracks.length) loadMoreBtn.style.display = 'none';
        });
      </script>
    </body>
    </html>
    """

    return render_template_string(html)


# ---------- ROUTE: /routine (GET renders form; POST returns routine) ----------

@app.route("/routine", methods=["GET", "POST"])
def routine():
    if not getattr(g, "user", None):
        return redirect(url_for("login"))

    # Helper to format times
    def fmt(dt):
        return dt.strftime("%I:%M %p")

    # Helper: safe parse time string "HH:MM" -> datetime using today's date (we only use time math)
    def parse_time(s):
        return datetime.strptime(s, "%H:%M")

    page_template = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>{{ ('Routine Planner') }}</title>
      <style>
        body { margin:0; padding:0; background:#f1f4f9; font-family: Arial, sans-serif; }
        .center-box { max-width:720px; margin:60px auto; background:white; padding:26px; border-radius:14px; box-shadow:0 6px 24px rgba(0,0,0,0.10); }
        h2 { margin-top:0; color:#233; }
        form .input { width:100%; padding:10px; margin:8px 0; border-radius:8px; border:1px solid #d0d7e6; font-size:15px; box-sizing:border-box; }
        .row { display:block; }
        button { width:100%; padding:12px; background:#4a6cf7; color:white; border:none; border-radius:10px; font-size:16px; cursor:pointer; }
        .back-home { display:inline-block; margin-top:12px; color:#4a6cf7; text-decoration:none; font-weight:600; }
        .timeline { margin-top:18px; }
        .item { padding:12px; border-left:4px solid #cfe6ff; background:#fcfeff; margin:10px 0; border-radius:8px; }
        .time { font-weight:700; margin-right:8px; color:#123; }
        .small { color:#666; font-size:14px; margin-top:6px; }
      </style>
    </head>
    <body>
      <div class="center-box">
        {% if not timeline %}
          <h2>{{ ('Create your calm daily routine') }}</h2>
          <form method="post">
            <label class="row">{{ ('Wake up time (HH:MM):') }}</label>
            <input class="input" type="time" name="wake" required>

            <label class="row">{{ ('Sleep time (HH:MM):') }}</label>
            <input class="input" type="time" name="sleep" required>

            <label class="row">{{ ('Work/Study hours per day (e.g. 4.5):') }}</label>
            <input class="input" type="number" step="0.1" min="0" max="24" name="work_hours" required>

            <label class="row">{{ ('Workout (optional):') }}</label>
            <input class="input" type="text" name="workout" placeholder="{{ ('e.g. light yoga') }}">

            <label class="row">{{ ('Hobby (optional, type None if no hobby):') }}</label>
            <input class="input" type="text" name="hobby" placeholder="{{ ('e.g. reading') }}">

            <button type="submit">{{ ('Generate Calm Routine') }}</button>
          </form>

          <a class="back-home" href="/">{{ '⬅ ' + ('Back to Home') }}</a>

        {% else %}
          <a class="back-home" href="/">{{ '⬅ ' + ('Back to Home') }}</a>
          <h2>{{ ('Your Calm & Gentle Full-Day Routine') }}</h2>

          <div class="small">{{ ('Wake') }}: <strong>{{ wake_display }}</strong> — {{ ('Sleep') }}: <strong>{{ sleep_display }}</strong> — {{ ('Work') }}: <strong>{{ work_hours }} hrs</strong></div>

          <div class="timeline">
            {% for it in timeline %}
            <div class="item">
              <div><span class="time">{{ it.time }}</span> — <span class="text">{{ it.text }}</span></div>
            </div>
            {% endfor %}
          </div>

        {% endif %}
      </div>
    </body>
    </html>
    """

    if request.method == "GET":
        return render_template_string(page_template, timeline=None)

    wake_s = request.form.get("wake", "")
    sleep_s = request.form.get("sleep", "")
    try:
        work_hours = float(request.form.get("work_hours", "0"))
    except ValueError:
        work_hours = 0.0
    workout = (request.form.get("workout") or "").strip()
    hobby = (request.form.get("hobby") or "").strip()
    if not hobby:
        hobby = "None"

    try:
        wake_dt = parse_time(wake_s)
        sleep_dt = parse_time(sleep_s)
    except Exception:
        return render_template_string(page_template, timeline=None)

    if sleep_dt <= wake_dt:
        sleep_dt = sleep_dt + timedelta(days=1)

    t = wake_dt
    timeline = []

    timeline.append({"time": fmt(t), "text": ("Wake up gently and take a few slow, mindful breaths to begin the day calmly.")})
    t += timedelta(minutes=8)

    timeline.append({"time": fmt(t), "text": ("Drink a glass of water to hydrate and help your body wake up.")})
    t += timedelta(minutes=7)

    timeline.append({"time": fmt(t), "text": ("Do gentle stretching or mobility exercises for about 12 minutes to loosen your body.")})
    t += timedelta(minutes=12)

    if workout:
        timeline.append({"time": fmt(t), "text": ("Spend %(workout)s for a gentle workout to refresh your energy.", workout==workout)})
        t += timedelta(minutes=20)

    timeline.append({"time": fmt(t), "text": ("Freshen up and prepare for the day—wash your face and get dressed comfortably.")})
    t += timedelta(minutes=12)

    timeline.append({"time": fmt(t), "text": ("Have a healthy, calming breakfast and sip water or herbal tea to start well.")})
    t += timedelta(minutes=30)

    # Lunch, work, breaks etc. logic as before, with texts wrapped in () for translation...

    # Example of translated timeline entries:
    lunch_time = wake_dt.replace(hour=13, minute=30)
    if lunch_time <= wake_dt:
        lunch_time += timedelta(days=1)

    timeline.append({"time": fmt(lunch_time), "text": ("Take a peaceful lunch now (around 1–2 PM) and eat slowly to relax.")})

    # Add wind-down and sleep entries with translations similarly
    winddown_start = sleep_dt - timedelta(minutes=75)
    if winddown_start <= t:
        winddown_start = t + timedelta(minutes=5)

    timeline.append({"time": fmt(winddown_start), "text": ("Start your wind-down routine: dim lights, avoid screens, breathe slowly and relax.")})
    timeline.append({"time": fmt(sleep_dt), "text": ("Go to bed peacefully with a calm mind and allow your body to rest.")})

    return render_template_string(page_template,
                                  timeline=timeline,
                                  wake_display=fmt(wake_dt),
                                  sleep_display=fmt(sleep_dt),
                                  work_hours=work_hours)



from flask import render_template_string

@app.route("/breathing")
def breathing():
    if not g.user:
        return redirect(url_for("login"))

    # English text
    title = "Breathing Exercise"
    intro_text = "Let's start a quick breathing exercise…"
    t_inhale = "Inhale..."
    t_hold = "Hold..."
    t_exhale = "Exhale..."
    back_text = "Back to Dashboard"
    
    html = """<!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>""" + title + """</title>
      <style>
        body {
          margin: 0;
          font-family: 'Segoe UI', sans-serif;
          background: #eaf7ef;
          text-align: center;
          color: #1b5e20;
        }

        h2 { font-size: 28px; margin-top: 18px; }

        #intro {
          font-size: 20px;
          margin-top: 6px;
          margin-bottom: 8px;
          font-weight: 600;
        }

        #instruction {
          font-size: 24px;
          font-weight: 700;
          height: 36px;
          margin-top: 6px;
        }

        #emoji {
          font-size: 42px;
          height: 50px;
          margin-top: 6px;
        }

        .box {
          width: 260px;
          height: 260px;
          border: 4px solid #333333;   /* darker box side as you asked */
          border-radius: 12px;
          margin: 18px auto;
          position: relative;
          background: #ffffff;
          box-shadow: 0 8px 20px rgba(0,0,0,0.04);
        }

        /* The moving line element (starts as a point) */
        #moving-line {
          position: absolute;
          background: #4caf50;
          border-radius: 6px;
        }

        .btn {
          display:inline-block;
          margin-top:12px;
          padding:10px 20px;
          background:#2e7d32;
          color:white;
          text-decoration:none;
          border-radius:8px;
        }
        .btn:hover { background:#1b5e20; }
      </style>
    </head>
    <body>
      <h2>🌿 """ + title + """</h2>

      <div id="intro">""" + intro_text + """</div>

      <div id="instruction">...</div>
      <div id="emoji">✨</div>

      <div class="box" id="box">
        <div id="moving-line"></div>
      </div>

      <a class="btn" href="/">""" + back_text + """</a>

      <script>
      (function(){
        // configuration
        const boxSize = 260;            // outer box px
        const border = 4;              // border width
        const inset = 10;              // inner inset so the line is fully inside
        const usable = boxSize - inset*2; // usable side length (240)
        const thickness = 10;          // line thickness (long line look)
        const phaseMs = 4000;          // 4 seconds per phase
        const gapBeforeStart = 2000;   // intro shown for 2 seconds

        // DOM
        const line = document.getElementById('moving-line');
        const instruction = document.getElementById('instruction');
        const emoji = document.getElementById('emoji');

        // localized phase texts (inserted from server)
        const phases = [
          { text: '""" + t_inhale + """', emoji: '🫁' },
          { text: '""" + t_hold + """',   emoji: '⏸' },
          { text: '""" + t_exhale + """', emoji: '💨' },
          { text: '""" + t_hold + """',   emoji: '⏸' }
        ];

        // helper to set immediate style (no transition)
        function setStyleNoTransition(el, props) {
          el.style.transition = 'none';
          for (const k in props) el.style[k] = props[k];
          // force reflow so next transition will work
          void el.offsetWidth;
        }

        // helper to animate with CSS transition
        function setStyleWithTransition(el, props, ms) {
          el.style.transition = 'all ' + (ms/1000) + 's linear';
          for (const k in props) el.style[k] = props[k];
        }

        // phase functions:
        // 0 = inhale (top: left -> right) : start point at top-left, grow width to usable and move to top-right
        function phaseInhale() {
          instruction.textContent = phases[0].text;
          emoji.textContent = phases[0].emoji;

          // start as point at top-left inside box
          setStyleNoTransition(line, {
            width: '0px',
            height: thickness + 'px',
            left: inset + 'px',
            top: inset + 'px'
          });

          // after tiny delay grow width toward right for 4s
          setTimeout(function(){
            setStyleWithTransition(line, {
              width: usable + 'px',
              left: inset + 'px',
              top: inset + 'px'
            }, phaseMs);
          }, 60);
        }

        // 1 = holdRight (right: top -> bottom) : start point at top-right, grow height downward
        function phaseHoldRight() {
          instruction.textContent = phases[1].text;
          emoji.textContent = phases[1].emoji;

          // position as point at top-right (we will switch to vertical)
          const rightX = inset + usable - thickness/2; // align inner vertical bar visually inside
          setStyleNoTransition(line, {
            width: thickness + 'px',
            height: '0px',
            left: (inset + usable - thickness/2) + 'px',
            top: inset + 'px'
          });

          setTimeout(function(){
            setStyleWithTransition(line, {
              height: usable + 'px',
              left: (inset + usable - thickness/2) + 'px',
              top: inset + 'px'
            }, phaseMs);
          }, 60);
        }

        // 2 = exhale (bottom: right -> left) : start point at bottom-right, grow width to the left
        function phaseExhale() {
          instruction.textContent = phases[2].text;
          emoji.textContent = phases[2].emoji;

          // starting at bottom-right as a point
          setStyleNoTransition(line, {
            width: '0px',
            height: thickness + 'px',
            left: (inset + usable) + 'px', // start slightly outside then animate leftwards
            top: (inset + usable) + 'px'
          });

          // animate leftwards to draw from right->left
          setTimeout(function(){
            // set left to inset and width to usable so the visible bar travels right->left
            // We'll move left from inset+usable to inset while width grows appropriately.
            // To mimic the "growing from a point into a line that reaches the other corner", we animate left and width.
            setStyleWithTransition(line, {
              left: inset + 'px',
              width: usable + 'px',
              top: (inset + usable) + 'px'
            }, phaseMs);
          }, 60);
        }

        // 3 = holdLeft (left: bottom -> top) : start point at bottom-left, grow height upward
        function phaseHoldLeft() {
          instruction.textContent = phases[3].text;
          emoji.textContent = phases[3].emoji;

          // position as point at bottom-left (vertical)
          setStyleNoTransition(line, {
            width: thickness + 'px',
            height: '0px',
            left: inset + 'px',
            top: (inset + usable) + 'px'
          });

          setTimeout(function(){
            // grow upward by increasing height and moving top to inset
            setStyleWithTransition(line, {
              height: usable + 'px',
              top: inset + 'px',
              left: inset + 'px'
            }, phaseMs);
          }, 60);
        }

        // orchestrator
        function startLoop() {
          // sequence: inhale -> holdRight -> exhale -> holdLeft
          phaseInhale();

          setTimeout(function(){
            phaseHoldRight();
          }, phaseMs + 100); // small buffer

          setTimeout(function(){
            phaseExhale();
          }, phaseMs*2 + 150);

          setTimeout(function(){
            phaseHoldLeft();
          }, phaseMs*3 + 200);

          // schedule next cycle slightly after 4 phases complete
          setTimeout(startLoop, phaseMs*4 + 300);
        }

        // start after showing intro for gapBeforeStart
        setTimeout(function(){
          // hide intro element (optional) to reduce visual clutter
          const introElm = document.getElementById('intro');
          if (introElm) introElm.style.visibility = 'hidden';

          // begin loop
          startLoop();
        }, gapBeforeStart);
      })();
      </script>
    </body>
    </html>"""

    return render_template_string(html)




# ---------- HISTORY ROUTE ----------

from datetime import datetime
from datetime import datetime
from flask import g, redirect, url_for, render_template_string
from datetime import datetime
from flask import g, redirect, url_for, render_template_string

from datetime import datetime
from flask import g, redirect, url_for, render_template_string

@app.route("/history")
def history():
    if not g.user:
        return redirect(url_for("login"))

    conn = get_db()
    # Fetch all entries for this user, most recent first
    results = conn.execute("""
        SELECT *
        FROM daily_checkup_history
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (g.user['id'],)).fetchall()
    conn.close()

    html = """
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      body { font-family:'Segoe UI', sans-serif; margin:0; padding:25px; background:linear-gradient(135deg,#dfe9f3 0%,#ffffff 100%); color:#003366; }
      h2 { text-align:center; color:#144a78; margin-bottom:25px; font-size:28px; letter-spacing:1px; }
      .table-container { width:85%; margin:auto; padding:20px; background:rgba(255,255,255,0.65); backdrop-filter:blur(8px); border-radius:16px; box-shadow:0 8px 25px rgba(0,0,0,0.15); }
      table { border-collapse:collapse; width:100%; overflow:hidden; border-radius:12px; }
      th { background:linear-gradient(120deg,#4a90e2,#357ab7); color:white; padding:14px; font-size:1.1em; border-bottom:3px solid #2b5d87; }
      td { padding:12px; text-align:center; border-bottom:1px solid #e5e5e5; font-size:15px; }
      tr:nth-child(even) { background:#f7faff; }
      tr:hover { background:#e6f0ff; transition:0.2s; }
      .menu { text-align:center; margin-top:25px; }
      .menu a { display:inline-block; margin:8px; padding:12px 20px; border-radius:10px; text-decoration:none; background:#4a90e2; color:white; font-weight:600; box-shadow:0 4px 12px rgba(0,0,0,0.25); transition:0.25s; }
      .menu a:hover { background:#2e6fb5; transform:translateY(-2px); }
    </style>
    </head>
    <body>
      <h2>📜 Your Complete Checkup History</h2>
      <div class="table-container">
        <table>
          <tr>
            <th>Date</th>
            <th>Time</th>
            <th>Mental Health Score</th>
            <th>Stress Score</th>
            <th>Burnout Risk</th>
          </tr>
    """

    for row in results:
        raw = str(row["created_at"])  # Ensure it's a string

        # Handle different timestamp formats
        try:
            if "T" in raw:  # ISO format like 2025-11-28T17:00:00
                dt = datetime.fromisoformat(raw)
            elif " " in raw:  # Standard format like 2025-11-28 17:00:00
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            else:  # Only date like 2025-11-28
                dt = datetime.strptime(raw, "%Y-%m-%d")
        except:
            # Fallback for irregular data
            parts = raw.split(" ")
            dt = datetime.strptime(parts[0], "%Y-%m-%d")
        
        date_clean = dt.strftime("%Y-%m-%d")
        time_clean = dt.strftime("%H:%M") if hasattr(dt, 'hour') else "00:00"

        # Correct way for sqlite3.Row to handle None
        mental = f"{float(row['mental_score'] or 0):.2f}"
        stress = f"{float(row['stress_score'] or 0):.2f}"
        burnout = f"{float(row['burnout_score'] or 0):.2f}"

        html += f"""
          <tr>
            <td>{date_clean}</td>
            <td>{time_clean}</td>
            <td>{mental}</td>
            <td>{stress}</td>
            <td>{burnout}</td>
          </tr>
        """

    html += """
        </table>
      </div>
      <div class="menu">
        <a href="/">🏠 Back to Home</a>
        <a href="/graph">View Graph</a>
      </div>
    </body>
    </html>
    """

    return render_template_string(html)

# ---------- GRAPH ROUTE ----------
from datetime import datetime
from datetime import datetime
import io
import base64
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from flask import g, redirect, url_for, render_template_string

@app.route("/graph")
def graph():
    if not g.user:
        return redirect(url_for("login"))

    conn = get_db()
    rows = conn.execute("""
        SELECT created_at, mental_score, stress_score, burnout_score
        FROM daily_checkup_history
        WHERE user_id=?
        ORDER BY created_at ASC
    """, (g.user['id'],)).fetchall()
    conn.close()

    if not rows:
        return "<h3>No past history found 😕</h3><p><a href='/'>Back to Dashboard</a></p>"

    # Extract full datetime objects
    timestamps = []
    for r in rows:
        raw = str(r["created_at"])
        try:
            if "T" in raw:  # ISO format
                dt = datetime.fromisoformat(raw)
            elif " " in raw:  # Standard format
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            else:  # Only date
                dt = datetime.strptime(raw, "%Y-%m-%d")
        except:
            dt = datetime.strptime(raw.split(" ")[0], "%Y-%m-%d")
        timestamps.append(dt)

    # Scores (handle None safely)
    mental = [round(float(r['mental_score'] or 0), 2) for r in rows]
    stress = [round(float(r['stress_score'] or 0), 2) for r in rows]
    burnout = [round(float(r['burnout_score'] or 0), 2) for r in rows]

    # PLOT AREA GRAPH
    plt.figure(figsize=(12,6))
    plt.plot(timestamps, mental, label='Mental Health', color='#4caf50', linewidth=2)
    plt.plot(timestamps, stress, label='Stress', color='#f44336', linewidth=2)
    plt.plot(timestamps, burnout, label='Burnout', color='#ff9800', linewidth=2)

    # Fill under lines
    plt.fill_between(timestamps, mental, alpha=0.2, color='#4caf50')
    plt.fill_between(timestamps, stress, alpha=0.2, color='#f44336')
    plt.fill_between(timestamps, burnout, alpha=0.2, color='#ff9800')

    plt.title("Your Past Checkup Scores", fontsize=16, weight='bold')
    plt.xlabel("Date & Time", fontsize=12)
    plt.ylabel("Score", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()

    # Format X-axis to show date + hour:minute
    plt.gca().xaxis.set_major_formatter(DateFormatter("%Y-%m-%d %H:%M"))
    plt.xticks(rotation=45, ha='right')

    # Convert plot to base64 image
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    buf.seek(0)
    img = base64.b64encode(buf.getvalue()).decode()

    # HTML output
    html = f"""
    <style>
      body {{
        font-family: 'Segoe UI', sans-serif;
        text-align:center;
        padding:30px;
        background:linear-gradient(135deg,#e3f2fd,#e8f5e9);
        color:#003366;
      }}
      img {{
        border-radius:12px;
        box-shadow:0 4px 12px rgba(0,0,0,0.1);
        max-width:95%;
      }}
      a {{
        display:inline-block;
        margin-top:20px;
        background:#4a90e2;
        color:#fff;
        padding:10px 14px;
        border-radius:8px;
        text-decoration:none;
      }}
      a:hover {{ background:#357ab7; }}
    </style>

    <h2>📊 Your Past Checkup Scores</h2>
    <img src='data:image/png;base64,{img}' alt='graph'/>
    <p><a href="/">🏠 Back to Home</a></p>
    """

    return render_template_string(html)


# --- Required imports for monthly_report routes (paste once near the top of app.py) ---
import io
from datetime import datetime, timedelta


from flask import g, redirect, url_for, render_template_string, send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import matplotlib.pyplot as plt
import os
import io
from datetime import datetime

# -----------------------------
# Daily Report Page
# -----------------------------
@app.route("/daily_report")
def daily_report():
    if not g.user:
        return redirect(url_for("login"))

    return render_template_string("""
    <html>
    <head>
    <style>
      body {
        font-family: 'Segoe UI', sans-serif;
        background: #eef3f9;
        margin: 0;
        padding: 0;
        text-align: center;
      }
      .container {
        width: 92%;
        max-width: 900px;
        margin: 40px auto;
        background: white;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 5px 25px rgba(0,0,0,0.15);
        overflow: visible;
      }
      h2 { font-size: 26px; color: #1b4b8a; margin-bottom: 20px; }
      .frame {
        width: 100%;
        height: 600px;
        border: 3px solid #1b4b8a;
        border-radius: 14px;
      }
      .btn {
        display: inline-block;
        padding: 12px 22px;
        margin: 12px 8px 0 8px;
        background: #1b4b8a;
        color: white;
        border-radius: 10px;
        text-decoration: none;
        font-weight: bold;
        transition: 0.25s;
      }
      .btn:hover {
        background: #144a78;
        transform: translateY(-2px);
      }
    </style>
    </head>

    <body>
      <div class="container">
        <h2>📄 Daily Mental Health Report</h2>

        <!-- PDF Iframe -->
        <iframe src="/daily_report_pdf#toolbar=0" class="frame"></iframe>

        <!-- Buttons below iframe -->
        <div>
          <a href="/daily_report_download" class="btn">⬇ Download PDF</a>
          <a href="/" class="btn">🏠 Back to Home</a>
        </div>
      </div>
    </body>
    </html>
    """)

# -----------------------------
# Helper function: generate daily PDF elements
# -----------------------------
def generate_daily_pdf_elements(user):
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'title', parent=styles['Heading1'], alignment=1,
        textColor=colors.HexColor("#1b4b8a"), fontSize=24, spaceAfter=25
    )
    elements.append(Paragraph("🧠 Daily Mental Health Report", title_style))
    elements.append(Spacer(1, 20))

    # User info
    name = user["name"]
    now = datetime.now().strftime("%d %B %Y • %I:%M %p")
    details_table = Table([["Name", name], ["Generated On", now]], colWidths=[120, 300])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#1b4b8a")),
        ('TEXTCOLOR', (0,0), (0,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#1b4b8a")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,-1), "Helvetica-Bold")
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 25))

    # Fetch latest daily checkup
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT created_at, mental_score, stress_score, burnout_score
        FROM daily_checkup_history
        WHERE user_id=?
        ORDER BY created_at DESC
        LIMIT 1
    """, (user['id'],))
    latest = cur.fetchone()
    conn.close()

    if latest:
        # Format date & time
        raw_ts = latest["created_at"]
        try:
            dt = datetime.fromisoformat(raw_ts)
        except:
            try:
                dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
            except:
                dt = datetime.strptime(raw_ts.split(" ")[0], "%Y-%m-%d")
        formatted_date = dt.strftime("%d %B %Y • %I:%M %p")

        # Table with all three scores
        result_table = Table([
            ["Checkup Date", formatted_date],
            ["Mental Score", f"{float(latest['mental_score']):.2f} / 10"],
            ["Stress Score", f"{float(latest['stress_score']):.2f} / 10"],
            ["Burnout Risk", f"{float(latest['burnout_score']):.2f} / 10"]
        ], colWidths=[150, 250])

        result_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#2e7d32")),
            ('TEXTCOLOR', (0,0), (0,-1), colors.white),
            ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#2e7d32")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.darkgreen),
            ('FONTNAME', (0,0), (-1,-1), "Helvetica-Bold")
        ]))
        elements.append(result_table)
    else:
        elements.append(Paragraph("No Daily Checkup data found.", ParagraphStyle('center', alignment=1)))

    elements.append(Spacer(1, 25))
    elements.append(Paragraph("✨ Remember: small steps each day create big results.", ParagraphStyle('footer', alignment=1)))

    return elements

# -----------------------------
# Daily Report PDF for iframe
# -----------------------------
@app.route("/daily_report_pdf")
def daily_report_pdf():
    if not g.user:
        return redirect(url_for("login"))

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = generate_daily_pdf_elements(g.user)
    pdf.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=False)

# -----------------------------
# Daily Report PDF Download (separate route)
# -----------------------------
@app.route("/daily_report_download")
def daily_report_download():
    if not g.user:
        return redirect(url_for("login"))

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = generate_daily_pdf_elements(g.user)
    pdf.build(elements)
    buf.seek(0)
    filename = f"Daily_Report_{datetime.today().strftime('%Y-%m-%d')}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)

# -----------------------------
# Monthly Report Page
# -----------------------------
@app.route("/monthly_report")
def monthly_report():
    if not g.user:
        return redirect(url_for("login"))

    return render_template_string("""
    <html>
    <head>
    <style>
      body {
        font-family: 'Segoe UI', sans-serif;
        background: #eef3f9;
        margin: 0;
        padding: 0;
        text-align: center;
      }
      .container {
        width: 92%;
        max-width: 900px;
        margin: 40px auto;
        background: white;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 5px 25px rgba(0,0,0,0.15);
        overflow: visible;
      }
      h2 { font-size: 26px; color: #1b4b8a; margin-bottom: 20px; }
      .frame {
        width: 100%;
        height: 550px;
        border: 3px solid #1b4b8a;
        border-radius: 14px;
      }
      .btn {
        display: inline-block;
        padding: 12px 22px;
        margin: 12px 8px 0 8px;
        background: #1b4b8a;
        color: white;
        border-radius: 10px;
        text-decoration: none;
        font-weight: bold;
        transition: 0.25s;
      }
      .btn:hover {
        background: #144a78;
        transform: translateY(-2px);
      }
    </style>
    </head>

    <body>
      <div class="container">
        <h2>📅 Monthly Mental Health Report</h2>

        <!-- PDF Iframe -->
        <iframe src="/monthly_report_pdf#toolbar=0" class="frame"></iframe>

        <!-- Buttons below iframe -->
        <div>
          <a href="/monthly_report_download" class="btn">⬇ Download PDF</a>
          <a href="/" class="btn">🏠 Back to Home</a>
        </div>
      </div>
    </body>
    </html>
    """)

# -----------------------------
# Helper function: generate PDF elements
# -----------------------------
def generate_monthly_pdf_elements(user):
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'title', parent=styles['Heading1'], alignment=1,
        fontSize=24, textColor=colors.HexColor("#1b4b8a")
    )
    elements.append(Paragraph("📅 Monthly Mental Health Report", title_style))
    elements.append(Spacer(1, 20))

    # User info
    name = user["name"]
    now = datetime.now().strftime("%d %B %Y • %I:%M %p")
    user_table = Table([["Name", name], ["Generated On", now]], colWidths=[120, 300])
    user_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#1b4b8a")),
        ('TEXTCOLOR', (0,0), (0,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#1b4b8a")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,-1), "Helvetica-Bold")
    ]))
    elements.append(user_table)
    elements.append(Spacer(1, 20))

    # Fetch current month data
    conn = get_db()
    cur = conn.cursor()
    today = datetime.today()
    first_day_month = today.replace(day=1).strftime("%Y-%m-%d")
    cur.execute("""
        SELECT created_at, mental_score, stress_score, burnout_score
        FROM daily_checkup_history
        WHERE user_id=? AND created_at >= ?
        ORDER BY created_at ASC
    """, (user['id'], first_day_month))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        elements.append(Paragraph("No monthly data available.", styles["Normal"]))
        return elements

    # Prepare graph data
    timestamps = []
    mental_scores = []
    stress_scores = []
    burnout_scores = []

    for r in rows:
        try:
            dt = datetime.fromisoformat(r["created_at"])
        except:
            dt = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
        timestamps.append(dt)
        mental_scores.append(float(r["mental_score"]))
        stress_scores.append(float(r["stress_score"]))
        burnout_scores.append(float(r["burnout_score"]))

    # Plot area graph
    temp_dir = "static/temp"
    os.makedirs(temp_dir, exist_ok=True)
    graph_path = os.path.join(temp_dir, "monthly_graph.png")

    plt.figure(figsize=(10,5))
    plt.plot(timestamps, mental_scores, label='Mental Health', color='#4caf50', linewidth=2)
    plt.plot(timestamps, stress_scores, label='Stress', color='#f44336', linewidth=2)
    plt.plot(timestamps, burnout_scores, label='Burnout', color='#ff9800', linewidth=2)

    plt.fill_between(timestamps, mental_scores, alpha=0.2, color='#4caf50')
    plt.fill_between(timestamps, stress_scores, alpha=0.2, color='#f44336')
    plt.fill_between(timestamps, burnout_scores, alpha=0.2, color='#ff9800')

    plt.title("Daily Scores - Current Month", fontsize=14)
    plt.xlabel("Date")
    plt.ylabel("Score")
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(graph_path, dpi=120)
    plt.close()

    # Insert graph into PDF
    elements.append(RLImage(graph_path, width=480, height=220))
    elements.append(Spacer(1, 20))

    # Average table
    avg_mental = sum(mental_scores)/len(mental_scores)
    avg_stress = sum(stress_scores)/len(stress_scores)
    avg_burnout = sum(burnout_scores)/len(burnout_scores)

    avg_table = Table([
        ["Avg Mental Score", f"{avg_mental:.2f} / 10"],
        ["Avg Stress Score", f"{avg_stress:.2f} / 10"],
        ["Avg Burnout Risk", f"{avg_burnout:.2f} / 10"]
    ])
    avg_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#2e7d32")),
        ('TEXTCOLOR', (0,0), (0,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#2e7d32")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.darkgreen),
        ('FONTNAME', (0,0), (-1,-1), "Helvetica-Bold")
    ]))
    elements.append(avg_table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("✨ Your mental health progress is growing every month!", styles["Normal"]))

    return elements

# -----------------------------
# Monthly Report PDF (for iframe)
# -----------------------------
@app.route("/monthly_report_pdf")
def monthly_report_pdf():
    if not g.user:
        return redirect(url_for("login"))

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = generate_monthly_pdf_elements(g.user)
    pdf.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=False)

# -----------------------------
# Monthly Report Download (separate route)
# -----------------------------
@app.route("/monthly_report_download")
def monthly_report_download():
    if not g.user:
        return redirect(url_for("login"))

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    elements = generate_monthly_pdf_elements(g.user)
    pdf.build(elements)
    buf.seek(0)

    filename = f"Monthly_Report_{datetime.today().strftime('%Y-%m')}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


# ------------------------
# GAMES MENU
# ------------------------
@app.route("/games")
def games():
    bg_img = "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1470&q=80"
    html = f"""
    <div style="
        background-image: url('{bg_img}');
        min-height: 100vh;
        background-size: cover;
        padding: 50px 20px;
        color: white;
        font-family: Arial, sans-serif;
        text-align: center;
    ">
        <h1>🎮 Choose a Game to Play</h1>
        <ul style="list-style: none; padding: 0; max-width: 400px; margin: 30px auto;">
            <li style="margin: 15px 0; background: #FFA726; border-radius: 12px; padding: 15px;">
                <a href="/mole_game" style="color: white; font-size: 20px; text-decoration: none; font-weight: bold;">
                    🐹 Mole Emoji Game
                </a>
            </li>
            <li style="margin: 15px 0; background: #66BB6A; border-radius: 12px; padding: 15px;">
                <a href="/memory_game" style="color: white; font-size: 20px; text-decoration: none; font-weight: bold;">
                    🃏 Memory Card Game
                </a>
            </li>
            <li style="margin: 15px 0; background: #42A5F5; border-radius: 12px; padding: 15px;">
                <a href="/zen_color" style="color: white; font-size: 20px; text-decoration: none; font-weight: bold;">
                    🎨 Zen Color Match
                </a>
            </li>
        </ul>
        <a href="/" style="color: #B0BEC5; font-size: 18px; text-decoration: underline;">← Back to Dashboard</a>
    </div>
    """
    return render_template_string(html)


# ------------------------
# MOLE GAME (Whack-a-Mole)
# ------------------------
@app.route("/mole_game")
def mole_game():
    html = """
    <html>
    <head>
        <title>🐹 Mole Emoji Game</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 30px; background: #f9fbe7; }
            .grid { display: grid; grid-template-columns: repeat(3, 100px); grid-gap: 20px; justify-content: center; }
            .hole { width: 100px; height: 100px; background: #8d6e63; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 50px; cursor: pointer; }
        </style>
        <script>
            let score = 0;
            function popMole() {
                let holes = document.querySelectorAll(".hole");
                holes.forEach(h => h.innerHTML = "");
                let idx = Math.floor(Math.random() * holes.length);
                holes[idx].innerHTML = "🐹";
            }
            function hit(hole) {
                if (hole.innerHTML === "🐹") {
                    score++;
                    document.getElementById("score").innerText = "Score: " + score;
                    hole.innerHTML = "";
                }
            }
            setInterval(popMole, 1000);
        </script>
    </head>
    <body>
        <h1>🐹 Whack-a-Mole Emoji Game</h1>
        <h2 id="score">Score: 0</h2>
        <div class="grid">
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
            <div class="hole" onclick="hit(this)"></div>
        </div>
        <br><a href="/games">⬅ Back to Games</a>
    </body>
    </html>
    """
    return html


# ------------------------
# MEMORY CARD GAME
# ------------------------

@app.route("/memory_game")
def memory_game():
    # ✅ 50 sets, each with 18 unique emojis
    emoji_sets = [
        ["🍎","🍌","🍇","🍉","🍒","🥕","🍓","🍋","🍊","🍍","🥭","🍑","🥥","🥦","🥬","🍆","🥒","🥔"],
        ["🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🐯","🦁","🐮","🐷","🐸","🐵","🐔","🐧","🐦"],
        ["⚽","🏀","🏈","⚾","🎾","🏐","🏉","🥏","🎱","🏓","🏸","🥅","🏒","🏑","🥍","🏏","⛳","🥊"],
        ["🚗","🚕","🚙","🚌","🚎","🏎","🚓","🚑","🚒","🚐","🚚","🚛","🚜","🛵","🏍","🚲","🛺","🚂"],
        ["😀","😁","😂","🤣","😃","😄","😅","😆","😉","😊","😋","😎","😍","😘","🥰","😗","😙","😚"],
        ["🌸","🌼","🌻","🌹","🥀","🌷","🌱","🌲","🌳","🌴","🌵","🌾","🌿","🍀","🍁","🍂","🍃","☘"],
        ["🪁","🎈","🎉","🎊","🎃","🎄","🎆","🎇","✨","🎍","🎎","🎏","🎐","🎑","🎀","🎁","🧧","🥮"],
        ["🛩","✈","🚀","🛸","🚁","⛵","🚤","🛥","🚢","🛳","⚓","🪝","🛶","🚡","🚠","🚟","🛰","🪂"],
        ["⌚","📱","💻","🖥","🖨","🖱","💽","💾","💿","📀","🎥","📷","📸","📞","☎","📺","📡","🔦"],
        ["❤","🧡","💛","💚","💙","💜","🖤","🤍","🤎","💔","❣","💕","💞","💓","💗","💖","💘","💝"],
        ["🥇","🥈","🥉","🏅","🎖","🏆","🏵","🎗","🎫","🎟","🎪","🤹","🎭","🎨","🎬","🎤","🎧","🎼"],
        ["📚","📖","📒","📕","📗","📘","📙","📓","📔","📑","🔖","📰","🗞","📊","📈","📉","🗂","📁"],
        ["🔑","🗝","🔨","🪓","⛏","⚒","🛠","🪚","🔧","🪛","🔩","⚙","🪤","🧰","🧲","🪜","⚖","🧱"],
        ["💣","🔪","🗡","⚔","🛡","🚬","⚰","⚱","🏺","🔮","📿","💈","⚗","🔭","🔬","🕳","💊","💉"],
        ["🌍","🌎","🌏","🌐","🗺","🗾","🧭","🏔","⛰","🌋","🗻","🏕","🏖","🏜","🏝","🏟","🏛","🏗"],
        ["🏠","🏡","🏘","🏚","🏢","🏬","🏣","🏤","🏥","🏦","🏨","🏩","🏪","🏫","🏭","🏯","🏰","⛪"],
        ["🐙","🦑","🦐","🦞","🦀","🐡","🐠","🐟","🐬","🐳","🐋","🦈","🐊","🐢","🦎","🐍","🐸","🦧"],
        ["🦒","🦓","🐎","🦌","🐪","🐫","🦙","🦥","🦦","🦨","🦘","🐘","🦏","🦛","🐐","🐏","🐑","🐄"],
        ["🛒","🎁","📦","📫","📬","📮","🗳","✉","📧","📩","📨","📤","📥","📦","📦","📦","📦","📦"],
        ["🧩","♟","🎲","🃏","🀄","🎴","🎮","🎰","🎯","🎳","🎮","🎮","🎮","🎮","🎮","🎮","🎮","🎮"],
        ["🌞","🌝","🌚","🌛","🌜","⭐","🌟","✨","⚡","🔥","💥","☄","🌠","🌌","🌃","🌆","🌇","🌉"],
        ["👩","👨","🧑","👧","👦","👶","👵","👴","🧓","👩‍🦰","👨‍🦰","👩‍🦱","👨‍🦱","👩‍🦳","👨‍🦳","👩‍🦲","👨‍🦲","🧔"],
        ["👩‍⚕","👨‍⚕","👩‍🎓","👨‍🎓","👩‍🏫","👨‍🏫","👩‍⚖","👨‍⚖","👩‍🌾","👨‍🌾","👩‍🍳","👨‍🍳","👩‍🔧","👨‍🔧","👩‍🏭","👨‍🏭","👩‍💻","👨‍💻"],
        ["✍","👀","👁","👂","👃","👄","👅","🦷","🦴","👤","👥","🫀","🫁","🧠","🦾","🦿","🦵","🦶"],
        ["🩰","🥋","🥊","🥌","⛸","🛷","🎿","⛷","🏂","🏋","🤼","🤸","⛹","🤺","🤾","🏌","🏇","🏄"],
        ["🛏","🛋","🚪","🪑","🪞","🪟","🪠","🚿","🛁","🚽","🪤","🧴","🪥","🧻","🪣","🛒","🧹","🧺"],
        ["🐕","🐩","🐕‍🦺","🦮","🐈","🐈‍⬛","🐅","🐆","🦓","🦍","🦧","🦣","🦘","🦬","🐂","🐃","🐄","🐎"],
        ["🍔","🍟","🌭","🍕","🥪","🌮","🌯","🥙","🥗","🥘","🥫","🍝","🍜","🍲","🍛","🍣","🍤","🍱"],
        ["🥧","🍦","🍧","🍨","🍩","🍪","🎂","🍰","🧁","🥮","🍫","🍬","🍭","🍮","🍯","🍼","🥛","☕"],
        ["🍵","🧃","🥤","🍶","🍺","🍻","🥂","🍷","🥃","🍸","🍹","🧉","🧊","🥄","🍴","🍽","🥢","🔪"],
        ["🦖","🦕","🐉","🐲","👾","🤖","🎃","👻","💀","☠","👽","👺","👹","🧟","🧛","🧙","🧚","🧞"],
        ["🎵","🎶","🎼","🎤","🎧","🎹","🥁","🎷","🎺","🎸","🪕","🎻","🪗","🎬","📽","🎥","🎞","📺"],
        ["💍","💎","📿","📯","🎺","🥁","🧿","🪬","🪙","💰","💴","💵","💶","💷","💸","💳","🧾","💹"],
        ["🚧","⛽","🚏","🚦","🚥","🛑","🚸","🏗","🧱","⚒","🛠","🪓","🔧","🪛","⚙","🧰","🪚","🔨"],
        ["🌪","🌈","☔","❄","☃","⛄","🌊","🌫","🌁","🌂","🌤","⛅","🌥","🌦","🌧","🌨","🌩","🌙"],
        ["✝","☪","🕉","☸","✡","🔯","🕎","☯","☦","🛐","⛩","🕌","🕋","⛪","🕍","🛕","🕉","♾"],
        ["📡","💻","⌨","🖱","🖲","🕹","💽","💾","💿","📀","📼","📷","📸","📹","🎥","📞","☎","📟"],
        ["🔔","🔕","📢","📣","📯","🔊","🔉","🔈","🔇","🎼","🎵","🎶","🎤","🎧","🎙","🎚","🎛","📻"],
        ["✏","🖊","🖋","🖌","🖍","📝","💼","📁","📂","🗂","📅","📆","🗒","🗓","📇","📋","📊","📈"],
        ["🔒","🔓","🔏","🔐","🔑","🗝","🛡","🔨","🪓","🧰","🪛","⚙","🪤","🧲","🪜","⚖","⛓","🔗"],
        ["🌐","🗺","🧭","🏔","⛰","🌋","🗻","🏕","🏖","🏜","🏝","🏟","🏛","🏗","🛖","🏚","🏘","🏠"],
        ["💡","🔦","🕯","🪔","🔌","🔋","🪫","⚡","☀","🌞","🔥","💥","✨","🌟","⭐","🌠","🌌","🌃"],
        ["🧵","🪡","🧶","👗","👕","👖","🧥","👚","👔","👙","👘","🥻","🩱","🩲","🩳","🥿","👠","👡"],
        ["👢","🧦","🧤","🧣","🎩","🧢","👒","🎓","👑","💍","👝","👜","💼","🎒","👓","🕶","🥽","🥼"],
        ["🌭","🍔","🍟","🍕","🥪","🥗","🥙","🌮","🌯","🥫","🍲","🥘","🍝","🍜","🍣","🍤","🍱","🍛"],
        ["🥞","🧇","🍳","🥚","🥯","🥖","🥐","🍞","🥨","🧀","🥩","🍗","🍖","🥓","🍤","🍣","🥟","🍢"],
        ["🧃","🥤","🍵","🍶","🍺","🍻","🥂","🍷","🥃","🍸","🍹","🧉","🧊","☕","🥛","🍼","🍾","🧋"]
    ]
    set_index = int(request.args.get("set", 1)) - 1
    if set_index >= len(emoji_sets):
        return """
        <h1>🎉 Congratulations!</h1>
        <p>You finished all memory game sets!</p>
        <a href="/games">⬅ Back to Games</a>
        """

    emojis = emoji_sets[set_index] * 2  # make 36 cards
    random.shuffle(emojis)

    cards_html = "".join(
        [f'<div class="card" data-emoji="{emoji}" onclick="flip(this)"></div>' for emoji in emojis]
    )

    html = f"""
    <html>
    <head>
        <title>🃏 Memory Card Game - Set {set_index+1}</title>
        <style>
            body {{ font-family: Arial; text-align: center; background: #e3f2fd; }}
            .grid {{ display: grid; grid-template-columns: repeat(6, 100px); grid-gap: 15px; justify-content: center; margin-top: 30px; }}
            .card {{ width: 100px; height: 100px; background: #90caf9; border-radius: 10px; font-size: 40px; display: flex; align-items: center; justify-content: center; cursor: pointer; }}
        </style>
        <script>
            let flipped = [];
            function flip(card) {{
                if (card.innerText !== "") return;
                card.innerText = card.dataset.emoji;
                flipped.push(card);
                if (flipped.length === 2) {{
                    setTimeout(() => {{
                        if (flipped[0].innerText !== flipped[1].innerText) {{
                            flipped[0].innerText = "";
                            flipped[1].innerText = "";
                        }}
                        flipped = [];
                    }}, 800);
                }}
            }}
        </script>
    </head>
    <body>
        <h1>🃏 Memory Card Game - Set {set_index+1}</h1>
        <div class="grid">
            {cards_html}
        </div>
        <br>
        <a href="/memory_game?set={set_index+2}">➡ Next Set</a><br>
        <a href="/games">⬅ Back to Games</a>
    </body>
    </html>
    """
    return html
    
# ------------------------
# ZEN COLOR MATCH GAME
# ------------------------
@app.route("/zen_color")
def zen_color():
    import random, colorsys

    level = int(request.args.get("level", 1))
    grid_size = min(3 + level, 10)  # up to 10x10

    # Base HSL color
    h = random.random()  # hue (0–1)
    s = 0.6 + random.random() * 0.4  # saturation 0.6–1
    l = 0.4 + random.random() * 0.3  # lightness 0.4–0.7

    # Convert base to RGB
    r, g, b = [int(x * 255) for x in colorsys.hls_to_rgb(h, l, s)]

    # Odd color: adjust lightness clearly
    diff = max(0.05, 0.25 - level * 0.01)  # starts easy, gets harder
    odd_l = max(0, min(1, l + random.choice([-diff, diff])))
    r2, g2, b2 = [int(x * 255) for x in colorsys.hls_to_rgb(h, odd_l, s)]

    # Odd position
    odd_row = random.randint(0, grid_size - 1)
    odd_col = random.randint(0, grid_size - 1)

    grid_html = ""
    for r_idx in range(grid_size):
        for c_idx in range(grid_size):
            color = f"rgb({r},{g},{b})"
            if r_idx == odd_row and c_idx == odd_col:
                color = f"rgb({r2},{g2},{b2})"
                grid_html += f'<div class="cell" style="background:{color}" onclick="correct()"></div>'
            else:
                grid_html += f'<div class="cell" style="background:{color}" onclick="wrong(this)"></div>'

    html = f"""
    <html>
    <head>
        <title>🎨 Zen Color Match - Level {level}</title>
        <style>
            body {{ text-align: center; background: #fafafa; font-family: Arial; }}
            .grid {{
                display: grid;
                grid-template-columns: repeat({grid_size}, 60px);
                grid-gap: 8px;
                justify-content: center;
                margin-top: 30px;
            }}
            .cell {{
                width: 60px; height: 60px;
                border-radius: 8px;
                cursor: pointer;
                transition: transform 0.2s, opacity 0.3s;
            }}
            .cell:hover {{ transform: scale(1.1); }}
            #msg {{ margin-top:20px; font-size:20px; }}
            #score {{ font-size:18px; margin:10px; }}
        </style>
        <script>
            let score = parseInt(localStorage.getItem("zen_score")) || 0;

            function updateScoreDisplay() {{
                document.getElementById("score").innerText = "🌟 Score: " + score;
            }}

            function correct() {{
                score += 10;
                localStorage.setItem("zen_score", score);
                updateScoreDisplay();
                document.getElementById("msg").innerHTML = "✅ Correct! Next level...";
                setTimeout(() => {{
                    window.location.href = "/zen_color?level={level+1}";
                }}, 1000);
            }}

            function wrong(el) {{
                score = Math.max(0, score - 5);
                localStorage.setItem("zen_score", score);
                updateScoreDisplay();
                el.style.opacity = 0.4;
                document.getElementById("msg").innerHTML = "❌ Try again!";
            }}

            window.onload = updateScoreDisplay;
        </script>
    </head>
    <body>
        <h1>🎨 Zen Color Match</h1>
        <h2>Level {level}</h2>
        <div id="score"></div>
        <div class="grid">{grid_html}</div>
        <div id="msg"></div>
        <br>
        <a href="/games">⬅ Back to Games</a>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    init_db()
    app.run(debug=True)


