"""
Email utilities for Training Container.
Self-contained to avoid import complexity inside the Docker container.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email(subject: str, html_content: str, to_email: str = None) -> bool:
    """
    Send email using SMTP credentials from environment variables.
    """
    # Load config from env (passed by VertexManager)
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    # Fallback to ALERT_EMAIL if specific recipient not provided
    recipient = to_email or os.getenv("ALERT_EMAIL")
    
    if not smtp_user or not smtp_password:
        logger.warning("SMTP credentials not found in environment. Skipping email.")
        return False
        
    if not recipient:
        logger.warning("No recipient email found. Skipping email.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = recipient

    # Attach HTML version
    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipient, msg.as_string())
        server.close()
        logger.info(f"Email sent successfully to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def get_training_success_html(model_name: str, job_id: str, metrics: Dict[str, Any]) -> str:
    """Generate HTML for training success"""
    
    # Format metrics list
    metrics_html = ""
    for k, v in metrics.items():
        if isinstance(v, float):
            v_fmt = f"{v:.4f}"
        else:
            v_fmt = str(v)
        metrics_html += f'<div style="background:white;padding:10px;border-radius:5px;box-shadow:0 1px 2px rgba(0,0,0,0.1);text-align:center;"><div style="font-size:20px;font-weight:bold;color:#28a745;">{v_fmt}</div><div style="font-size:12px;color:#666;text-transform:uppercase;">{k}</div></div>'

    return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 Training Complete!</h1>
        <p>Model <strong>{model_name}</strong> has finished fine-tuning.</p>
    </div>
    <div class="content">
        <p>Your fine-tuning job has successfully completed. The model adapters have been saved to Cloud Storage and registered.</p>
        
        <h3>📊 Performance Metrics</h3>
        <div class="metrics-grid">
            {metrics_html}
        </div>
        
        <p style="font-size:12px;color:#666;margin-top:20px;">
            Job ID: {job_id}<br>
            Model: {model_name}
        </p>
    </div>
</body>
</html>
"""

def get_training_failure_html(model_name: str, job_id: str, error: str) -> str:
    """Generate HTML for training failure"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
        .error-box {{ background: #fff3cd; border: 1px solid #ffc107; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; font-family: monospace; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>❌ Training Failed</h1>
        <p>Model <strong>{model_name}</strong> encountered an error.</p>
    </div>
    <div class="content">
        <p>Unfortunately, the fine-tuning job failed to complete.</p>
        
        <h3>Error Details:</h3>
        <div class="error-box">{error}</div>
        
        <p>Please check the logs in Vertex AI console for more details.</p>
        
        <p style="font-size:12px;color:#666;margin-top:20px;">
            Job ID: {job_id}<br>
            Model: {model_name}
        </p>
    </div>
</body>
</html>
"""
