"""
Email Utility for sending notifications via SMTP.
Authenticated via Gmail App Password.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Union, Dict
import logging

# Configure logging
logger = logging.getLogger(__name__)

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_SENDER = os.getenv("EMAIL_SENDER", SMTP_USER)
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "mlopsproject25@gmail.com")


def send_email(
    to_email: Union[str, List[str]],
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """
    Send an email using configured SMTP server.
    
    Args:
        to_email: Data receiver email or list of emails
        subject: Email subject
        html_content: HTML body content
        text_content: Optional fallback text content
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Email sending skipped.")
        return False

    if isinstance(to_email, str):
        recipients = [to_email]
    else:
        recipients = to_email

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = ", ".join(recipients)

    # Attach text version (optional)
    if text_content:
        part1 = MIMEText(text_content, "plain")
        msg.attach(part1)

    # Attach HTML version
    part2 = MIMEText(html_content, "html")
    msg.attach(part2)

    try:
        # Create secure SMTP connection
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        
        # Login
        server.login(SMTP_USER, SMTP_PASSWORD)
        
        # Send
        server.sendmail(EMAIL_SENDER, recipients, msg.as_string())
        
        # Cleanup
        server.close()
        
        logger.info(f"Email sent successfully to {recipients}")
        print(f"[Email] Sent '{subject}' to {recipients}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        print(f"[Email] Failed to send to {recipients}: {e}")
        return False
