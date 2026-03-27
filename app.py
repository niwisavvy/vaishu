import io
import re
import time
import base64
import sqlite3
from collections import defaultdict
from email.utils import parseaddr

import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Email System", layout="wide")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("emails.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT,
    status TEXT,
    sent_at TEXT
)
""")

conn.commit()

# ---------------- LOGIN ----------------
USERS = {
    "user1": "pass1",
    "user2": "pass2"
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if USERS.get(u) == p:
            st.session_state.logged_in = True
            st.session_state.username = u
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

username = st.session_state.username

# ---------------- HELPERS ----------------
def clean_email(email):
    _, addr = parseaddr(email)
    return addr if "@" in addr else None

def safe_format(template, mapping):
    return template.format_map(defaultdict(str, mapping))

def format_name(name):
    if not name:
        return ""
    parts = name.strip().split()
    parts = [p.capitalize() for p in parts]

    if len(parts[0]) == 1 and len(parts) > 1:
        return f"Mr {parts[1]}"
    return parts[0]

def track_pixel(email):
    encoded = base64.b64encode(email.encode()).decode()
    return f"https://dummyimage.com/1x1/000/fff.png&text={encoded}"

def log_email(user, email, status):
    c.execute(
        "INSERT INTO email_logs (username, email, status, sent_at) VALUES (?, ?, ?, datetime('now'))",
        (user, email, status)
    )
    conn.commit()

def get_sent_emails(user):
    df = pd.read_sql_query(
        f"SELECT email FROM email_logs WHERE username='{user}' AND status='SENT'",
        conn
    )
    return set(df["email"].tolist())

# ---------------- UI ----------------
st.title("📧 Email Dashboard")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

from_email = st.text_input("Your Email")
app_password = st.text_input("App Password", type="password")

subject = st.text_input("Subject")
body = st.text_area("Body")

col1, col2 = st.columns(2)
send_btn = col1.button("🚀 Send")
stop_btn = col2.button("⛔ Stop")

# ---------------- DASHBOARD ----------------
st.subheader("📊 Dashboard")

df_logs = pd.read_sql_query(
    f"SELECT * FROM email_logs WHERE username='{username}' ORDER BY id DESC",
    conn
)

st.metric("Total Sent", len(df_logs))
st.metric("Failures", len(df_logs[df_logs["status"] == "FAILED"]))

st.dataframe(df_logs.head(20))

# ---------------- SEND LOGIC ----------------
if send_btn and uploaded_file:

    df = pd.read_csv(uploaded_file)
    sent_emails = get_sent_emails(username)

    st.info(f"Already sent: {len(sent_emails)} emails")

    for idx, row in df.iterrows():

        if stop_btn:
            break

        email = clean_email(row.get("email"))
        if not email or email in sent_emails:
            continue

        name = format_name(row.get("name", ""))

        body_final = safe_format(body, {"name": name})

        pixel = track_pixel(email)

        html = f"""
        <html>
        <body>
        <pre>{body_final}</pre>
        <img src="{pixel}" width="1" height="1">
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = email
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))

        success = False

        for _ in range(3):  # retry
            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.starttls()
                    server.login(from_email, app_password)
                    server.send_message(msg)
                success = True
                break
            except:
                time.sleep(3)

        if success:
            log_email(username, email, "SENT")
            st.success(f"Sent → {email}")
        else:
            log_email(username, email, "FAILED")
            st.error(f"Failed → {email}")

        time.sleep(3)

    st.success("Completed")

# ---------------- FOLLOW UPS ----------------
st.subheader("🔁 Follow-ups")

if st.button("Send Follow-ups"):
    pending = pd.read_sql_query(
        f"SELECT email FROM email_logs WHERE username='{username}' AND status='SENT'",
        conn
    )

    for _, row in pending.iterrows():
        st.write(f"Follow-up → {row['email']}")
        time.sleep(2)
