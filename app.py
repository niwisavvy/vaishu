import io
import re
import time
import base64
import sqlite3
from collections import defaultdict
from datetime import datetime

import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr

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
    opened INTEGER DEFAULT 0,
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
def clean_value(val):
    if isinstance(val, str):
        return val.replace("\xa0", " ").replace("\u200b", "").strip()
    return val

def clean_email_address(raw_email):
    if not raw_email:
        return None
    _, addr = parseaddr(raw_email)
    return addr if "@" in addr else None

def clean_display_name(name):
    if not name:
        return ""
    return name.replace("\xa0", " ").replace("\u200b", "").strip()

def clean_invisible_unicode(s):
    if not isinstance(s, str):
        return s
    return s.replace('\xa0', '').replace('\u200b', '').strip()

def safe_format(template, mapping):
    return template.format_map(defaultdict(str, mapping))

def format_name(full_name):
    if not full_name:
        return ""

    parts = full_name.strip().split()
    parts = [p.capitalize() for p in parts]

    if len(parts[0]) == 1 and len(parts) > 1:
        return f"Mr {parts[1]}"

    prefixes = {"Dr", "Mr", "Mrs", "Ms", "Prof"}
    if parts[0] in prefixes and len(parts) > 1:
        return f"{parts[0]} {parts[1]}"

    return parts[0]

def track_pixel(email):
    encoded = base64.b64encode(email.encode()).decode()
    return f"https://dummyimage.com/1x1/000/fff.png&text={encoded}"

def log_email(user, email, status):
    c.execute(
        "INSERT INTO email_logs (username, email, status, sent_at) VALUES (?, ?, ?, ?)",
        (user, email, status, datetime.now())
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
from_name = st.text_input("Your Name")

subject1 = st.text_input("Subject 1")
subject2 = st.text_input("Subject 2")

body1 = st.text_area("Body 1")
body2 = st.text_area("Body 2")

col1, col2 = st.columns(2)
send_btn = col1.button("🚀 Send")
follow_btn = col2.button("🔁 Send Follow-ups")

# ---------------- DASHBOARD ----------------
st.subheader("📊 Dashboard")

df_logs = pd.read_sql_query(
    f"SELECT * FROM email_logs WHERE username='{username}' ORDER BY id DESC",
    conn
)

total_sent = len(df_logs[df_logs["status"] == "SENT"])
failed = len(df_logs[df_logs["status"] == "FAILED"])
opened = df_logs["opened"].sum()

open_rate = (opened / total_sent * 100) if total_sent > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("Sent", total_sent)
col2.metric("Failed", failed)
col3.metric("Open Rate", f"{open_rate:.1f}%")

st.dataframe(df_logs.head(20))

# ---------------- SEND ----------------
if send_btn and uploaded_file:

    df = pd.read_csv(uploaded_file)
    df = df.applymap(clean_value)

    sent_emails = get_sent_emails(username)

    for idx, row in df.iterrows():

        email = clean_email_address(row.get("email"))
        if not email or email in sent_emails:
            continue

        full_name = row.get("name", "")
        first_name = format_name(full_name)

        mapping = dict(row)
        mapping["name"] = first_name

        if idx % 2 == 0:
            subject = safe_format(subject1, mapping)
            body = safe_format(body1, mapping)
        else:
            subject = safe_format(subject2, mapping)
            body = safe_format(body2, mapping)

        pixel = track_pixel(email)

        html = f"""
        <html>
        <body style="font-family: 'Times New Roman', serif;">
        <pre style="font-family: 'Times New Roman', serif;">{body}</pre>
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

        for _ in range(3):
            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.starttls()
                    server.login(from_email, app_password)
                    server.send_message(msg)
                success = True
                break
            except:
                time.sleep(2)

        if success:
            log_email(username, email, "SENT")
            st.success(f"Sent → {email}")
        else:
            log_email(username, email, "FAILED")
            st.error(f"Failed → {email}")

        time.sleep(2)

    st.success("Completed")

# ---------------- FOLLOW UPS ----------------
if follow_btn:

    sent_df = pd.read_sql_query(
        f"SELECT email FROM email_logs WHERE username='{username}' AND status='SENT'",
        conn
    )

    for _, row in sent_df.iterrows():
        st.info(f"Follow-up → {row['email']}")
        time.sleep(1)
