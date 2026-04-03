import os
import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime
from dotenv import load_dotenv

# Load credentials from .env (Must be in the root directory)
load_dotenv()

def triage_email(subject, sender):
    """CEM501 Framework: Categorizes emails based on construction priority."""
    subject = subject.lower()
    
    # URGENT: Safety, stop work, or legal deadlines
    if any(word in subject for word in ["stop work", "safety", "urgent", "incident", "notice of delay", "penalty"]):
        return "URGENT"
    
    # ACTION: Tasks requiring response (RFIs, submittals, etc.)
    elif any(word in subject for word in ["rfi", "submittal", "review", "approval", "clarification", "concrete", "pier"]):
        return "ACTION"
    
    # FYI: General updates and daily records
    elif any(word in subject for word in ["update", "recap", "photos", "minutes", "daily log", "progress"]):
        return "FYI"
    
    # ARCHIVE: Everything else
    else:
        return "ARCHIVE"

def clean_body(raw_html):
    """Strips HTML tags and returns a clean text preview."""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', raw_html).strip()
    return " ".join(text.split())[:200]

def main():
    try:
        # 1. Server Connection
        mail = imaplib.IMAP4_SSL(os.getenv("IMAP_SERVER"))
        mail.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
        mail.select("INBOX")

        # 2. Precise Filter: Only from Instructor AND specifically between March 31 - April 2
        # This ignores any personal emails from today or earlier weeks.
        search_criterion = '(SINCE "31-Mar-2026" BEFORE "02-Apr-2026" FROM "eyuphan.koc@gmail.com")'
        status, messages = mail.search(None, search_criterion)
        
        ids = messages[0].split()
        
        if not ids:
            print("\n[!] No simulation emails found in the specified date range.")
            return

        print(f"\n{'='*75}")
        print(f"{'PROJECT CORRESPONDENCE TRIAGE: SIMULATION WINDOW':^75}")
        print(f"{'RANGE: MARCH 31 - APRIL 2, 2026':^75}")
        print(f"{'='*75}\n")

        results = []
        for mail_id in reversed(ids):
            _, data = mail.fetch(mail_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            
            # Subject Decoding
            subject_header = decode_header(msg["Subject"])[0]
            subject = subject_header[0]
            if isinstance(subject, bytes):
                encoding = subject_header[1] or "utf-8"
                subject = subject.decode(encoding)
            
            sender = msg.get("From")
            
            # Content Extraction
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()

            # Apply Triage Logic
            category = triage_email(subject, sender)
            results.append((category, sender, subject, clean_body(body)))

        # 3. Sort by priority hierarchy
        priority_map = {"URGENT": 0, "ACTION": 1, "FYI": 2, "ARCHIVE": 3}
        results.sort(key=lambda x: priority_map.get(x[0], 4))

        # 4. Professional Dashboard Output
        for cat, snd, sub, pre in results:
            icon = "🚨" if cat == "URGENT" else "📅" if cat == "ACTION" else "📋"
            print(f"[{cat:^8}] {icon} SUBJECT: {sub}")
            print(f"           FROM   : {snd}")
            print(f"           PREVIEW: {pre}...")
            print(f"{'-'*75}")

        mail.logout()
        print(f"\n{'='*75}")
        print(f"{'END OF LIVE SIMULATION REPORT':^75}")
        print(f"{'='*75}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()