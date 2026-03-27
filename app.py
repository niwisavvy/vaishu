import io
import re
import time
from collections import defaultdict
from email.header import Header
from email.utils import formataddr, parseaddr

import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Team Niwrutti")

# --- SMTP Settings ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
USE_TLS = True

# ---------------- Helpers ----------------
def clean_value(val):
    if isinstance(val, str):
        return val.replace("\xa0", " ").replace("\u200b", "").strip()
    return val

def clean_email_address(raw_email: str):
    if not raw_email:
        return None
    raw_email = clean_value(raw_email)
    _, addr = parseaddr(raw_email)
    if not addr:
        addr = re.sub(r"[<>\s\"']", "", raw_email)
    addr = addr.strip()
    if "@" not in addr:
        return None
    return addr

def safe_format(template: str, mapping: dict) -> str:
    return template.format_map(defaultdict(str, mapping))

def clean_display_name(name: str):
    if not name:
        return ""
    return name.replace("\xa0", " ").replace("\u200b", "").strip()

def clean_invisible_unicode(s: str):
    if not isinstance(s, str):
        return s
    return s.replace('\xa0', '').replace('\u200b', '').strip()

# ✅ NAME FORMATTER (FIXED)
def format_name(full_name):
    if not full_name:
        return ""

    prefixes = {"dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "prof", "prof."}
    parts = full_name.strip().split()

    if not parts:
        return ""

    parts = [p.capitalize() for p in parts]
    first_word = parts[0].lower()

    if first_word in prefixes:
        if len(parts) > 1:
            return f"{parts[0].replace('.', '')} {parts[1]}"
        return parts[0].replace(".", "")

    if len(parts[0]) == 1 and len(parts) > 1:
        return f"Mr {parts[1]}"

    return parts[0]

# ---------------- UI ----------------
st.title("Team Niwrutti")
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

# Email config
from_email = clean_invisible_unicode(st.text_input("Your Email"))
app_password = clean_invisible_unicode(st.text_input("App Password", type="password"))
from_name = st.text_input("Your Name")

# Templates
subject_tpl_1 = st.text_input("Subject 1")
subject_tpl_2 = st.text_input("Subject 2")

body_tpl_1 = st.text_area("Body 1", height=200)
body_tpl_2 = st.text_area("Body 2", height=200)

send_btn = st.button("Send Emails")

# ---------------- SEND LOGIC ----------------
if send_btn and uploaded_file:

    df = pd.read_csv(uploaded_file)
    df = df.applymap(clean_value)

    total = len(df)
    sent = 0

    progress = st.progress(0)

    for idx, row in df.iterrows():

        rowd = {str(k): clean_value(v) for k, v in row.to_dict().items()}

        recip_addr = clean_email_address(rowd.get("email", ""))
        if not recip_addr:
            continue

        rowd.setdefault("name", "")
        full_name = rowd.get("name", "")
        formatted_name = format_name(full_name)

        # ✅ SUBJECT (FULL NAME)
        subject_mapping = dict(rowd)
        subject_mapping["name"] = full_name

        # ✅ BODY (FORMATTED NAME)
        body_mapping = dict(rowd)
        body_mapping["name"] = formatted_name

        # 🔁 Alternate templates
        if sent % 2 == 0:
            subj_text = safe_format(subject_tpl_1, subject_mapping)
            body_text = safe_format(body_tpl_1, body_mapping)
        else:
            subj_text = safe_format(subject_tpl_2, subject_mapping)
            body_text = safe_format(body_tpl_2, body_mapping)

        # ✅ FIXED HTML (NO MONOSPACE)
        body_html = body_text.replace("\n", "<br>")

        html = f"""
        <html>
          <body style="font-family: 'Times New Roman', serif; font-size:14px; line-height:1.2;">
            {body_html}
          </body>
        </html>
        """

        msg = MIMEMultipart()

        from_header = formataddr((str(Header(from_name, "utf-8")), from_email))
        to_header = formataddr((str(Header(full_name, "utf-8")), recip_addr))

        msg["From"] = from_header
        msg["To"] = to_header
        msg["Subject"] = str(Header(subj_text, "utf-8"))

        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            if USE_TLS:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(from_email, app_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                    server.login(from_email, app_password)
                    server.send_message(msg)

            sent += 1
            st.success(f"✅ Sent to {recip_addr}")

        except Exception as e:
            st.error(f"❌ Failed: {recip_addr} | {e}")

        progress.progress((idx + 1) / total)

        # Delay
        time.sleep(2)

    st.success(f"Done — Sent {sent} emails")
