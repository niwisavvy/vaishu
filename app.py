import io
import re
import time
import os
from datetime import datetime, timedelta
from collections import defaultdict
from email.header import Header
from email.utils import formataddr, parseaddr

import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Team Niwrutti", layout="wide")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
USE_TLS = True

# ---------------- LOGIN ----------------
USERS = {
    "admin": os.getenv("APP_PASSWORD", "admin123"),
    "user1": os.getenv("APP_PASSWORD", "user123")
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if USERS.get(username) == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

username = st.session_state.username
progress_file = f"progress_{username}.txt"

# ---------------- HELPERS ----------------
def clean_value(val):
    if isinstance(val, str):
        return val.replace("\xa0", " ").replace("\u200b", "").strip()
    return val

def clean_email_address(raw_email):
    if not raw_email:
        return None
    _, addr = parseaddr(raw_email)
    if "@" not in addr:
        return None
    return addr.strip()

def safe_format(template, mapping):
    return template.format_map(defaultdict(str, mapping))

def format_first_name(full_name):
    if not full_name:
        return ""

    prefixes = {"dr", "mr", "mrs", "ms", "prof"}
    parts = [p.capitalize() for p in full_name.strip().split()]

    if not parts:
        return ""

    if parts[0].lower() in prefixes and len(parts) > 1:
        return f"{parts[0]} {parts[1]}"

    if len(parts[0]) == 1 and len(parts) > 1:
        return f"Mr {parts[1]}"

    return parts[0]

# ---------------- UI ----------------
st.title("📧 Email Campaign Dashboard")

tab1, tab2 = st.tabs(["📤 Campaign", "📊 Dashboard"])

# ================= TAB 1 =================
with tab1:
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    df = None
    if uploaded_file:
        df = pd.read_csv(uploaded_file).applymap(clean_value)
        st.dataframe(df)

    col1, col2 = st.columns(2)

    with col1:
        from_email = st.text_input("Sender Email")
        password = st.text_input("App Password", type="password")
        from_name = st.text_input("Sender Name")

    with col2:
        subject_1 = st.text_input("Subject 1")
        subject_2 = st.text_input("Subject 2")

    body_1 = st.text_area("Email Body 1", height=200)
    body_2 = st.text_area("Email Body 2", height=200)

    st.subheader("⏰ Campaign Schedule")
    delay1 = st.number_input("Reminder 1 (days)", value=2)
    delay2 = st.number_input("Reminder 2 (days)", value=4)
    delay3 = st.number_input("Reminder 3 (days)", value=6)

    send_clicked = st.button("🚀 Start Campaign")

# ================= CAMPAIGN LOGIC =================
if send_clicked and df is not None:

    # Resume
    start_index = 0
    try:
        with open(progress_file, "r") as f:
            start_index = int(f.read().strip())
    except:
        pass

    total = len(df)
    sent = 0
    failed = []

    progress = st.progress(0)

    for idx, row in df.iloc[start_index:].iterrows():

        rowd = row.to_dict()
        email = clean_email_address(rowd.get("email"))

        if not email:
            continue

        name = format_first_name(rowd.get("name", ""))

        subject = subject_1 if sent % 2 == 0 else subject_2
        body = body_1 if sent % 2 == 0 else body_2

        body = safe_format(body, {"name": name})

        # TRACKING PIXEL
        tracking_id = f"{username}_{idx}"
        pixel = f'<img src="https://yourdomain.com/track/{tracking_id}" width="1" height="1">'

        html_body = f"""
        <html>
        <body>
        <pre>{body}</pre>
        {pixel}
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg["From"] = formataddr((from_name, from_email))
        msg["To"] = email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(from_email, password)
                server.send_message(msg)

            sent += 1

            # SAVE PROGRESS
            with open(progress_file, "w") as f:
                f.write(str(idx + 1))

            st.success(f"Sent to {email}")

            # 🧊 delay
            time.sleep(5)

        except Exception as e:
            failed.append(rowd)

        progress.progress((idx + 1) / total)

    st.success(f"Campaign Completed. Sent: {sent}")

    # SAVE FAILED
    if failed:
        pd.DataFrame(failed).to_csv("failed.csv", index=False)

# ================= TAB 2 =================
with tab2:
    st.subheader("📊 Dashboard")

    sent_count = 0
    try:
        with open(progress_file, "r") as f:
            sent_count = int(f.read().strip())
    except:
        pass

    st.metric("Emails Sent", sent_count)

    if os.path.exists("failed.csv"):
        st.download_button(
            "Download Failed Emails",
            data=open("failed.csv").read(),
            file_name="failed.csv"
        )
