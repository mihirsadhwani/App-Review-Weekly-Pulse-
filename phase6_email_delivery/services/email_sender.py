import os
import smtplib
from email.message import EmailMessage
from datetime import datetime

from services.config_loader import get_config
from services.gemini_client import generate_text, LLMError

DEFAULT_INTRO = "Please find below the weekly user feedback pulse for Groww Mutual Fund."

class EmailSender:
    def __init__(self, input_pulse_path: str, output_draft_md: str, output_draft_txt: str):
        self.input_pulse_path = input_pulse_path
        self.output_draft_md = output_draft_md
        self.output_draft_txt = output_draft_txt
        
        # Load SMTP settings using priority helper
        self.smtp_host = get_config("SMTP_HOST")
        self.smtp_port = get_config("SMTP_PORT")
        self.smtp_user = get_config("SMTP_USER")
        self.smtp_password = get_config("SMTP_PASSWORD")
        self.smtp_tls = (get_config("SMTP_TLS") or "true").lower() == "true"
        self.default_to = get_config("EMAIL_TO")

    def draft_intro(self, pulse_content: str) -> str:
        """Ask Gemini for a short, professional intro line; fall back to the static template."""
        prompt = (
            "Write a 1-2 sentence introduction for an internal email to product leadership that "
            "contains the weekly app review pulse below. Mention the single most important signal. "
            "Plain text only, no greeting, no sign-off, no markdown.\n\nPulse:\n" + pulse_content
        )
        try:
            intro = generate_text(prompt, label="email_intro", temperature=0.3)
            return intro if intro and len(intro) < 500 else DEFAULT_INTRO
        except LLMError as e:
            print(f"Email intro generation failed, using template: {e}")
            return DEFAULT_INTRO

    def format_email_content(self, pulse_content: str, is_markdown: bool = False, intro: str = DEFAULT_INTRO) -> str:
        lines = [
            "Hi Team,",
            "",
            intro,
            "",
            pulse_content,
            "",
            "Regards",
            "Product Feedback Bot"
        ]
        return "\n".join(lines)

    def process(self, send_mode: bool = False, recipient: str = None):
        print("Phase 6 started: Email Draft & Delivery")
        
        if not os.path.exists(self.input_pulse_path):
            raise FileNotFoundError(f"Missing input pulse file: {self.input_pulse_path}")
            
        with open(self.input_pulse_path, 'r', encoding='utf-8') as f:
            pulse_content = f.read().strip()
            
        # Determine Recipient
        final_recipient = recipient if recipient else self.default_to
            
        # Subject
        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"[Weekly Pulse] Groww Mutual Fund Reviews — Week of {date_str}"
        
        # Email Body
        intro = self.draft_intro(pulse_content)
        body_md = f"Subject: {subject}\nTo: {final_recipient}\n\n" + self.format_email_content(pulse_content, True, intro)
        
        pulse_txt_path = self.input_pulse_path.replace(".md", ".txt")
        if os.path.exists(pulse_txt_path):
            with open(pulse_txt_path, 'r', encoding='utf-8') as f:
                pulse_content_txt = f.read().strip()
        else:
            pulse_content_txt = pulse_content
            
        body_txt = f"Subject: {subject}\nTo: {final_recipient}\n\n" + self.format_email_content(pulse_content_txt, False, intro)
        
        # Ensure directory exists
        output_dir = os.path.dirname(self.output_draft_md)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
        # Save drafts locally
        with open(self.output_draft_md, 'w', encoding='utf-8') as f:
            f.write(body_md)
            
        with open(self.output_draft_txt, 'w', encoding='utf-8') as f:
            f.write(body_txt)
            
        print("Email draft generated.")
        
        # Delivery logic
        if send_mode:
            print("Send Mode — Attempting SMTP delivery...")
            if not all([self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password, final_recipient]):
                raise RuntimeError("Missing SMTP configuration or recipient.")
                
            try:
                msg = EmailMessage()
                msg.set_content(self.format_email_content(pulse_content_txt, False, intro))
                msg['Subject'] = subject
                msg['From'] = self.smtp_user
                msg['To'] = final_recipient
                
                port = int(self.smtp_port)
                # Secure connection
                server = smtplib.SMTP(self.smtp_host, port)
                if self.smtp_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                server.quit()
                print("Email successfully sent.")
            except Exception as e:
                print(f"SMTP ERROR: {e}")
                raise RuntimeError(f"SMTP delivery failed: {e}") from e
        else:
            print("Dry Run Mode — Email draft generated but not sent.")
            
