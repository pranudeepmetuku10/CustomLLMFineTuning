"""
Email Templates for Pipeline Notifications

HTML email templates for dataset processing notifications.
"""

from typing import Dict, Optional
from datetime import datetime


def get_success_email_html(
    user_name: str,
    dataset_name: str,
    dataset_id: str,
    stats: Dict,
) -> str:
    """
    Generate HTML email for successful dataset processing.
    
    Args:
        user_name: User's name or email
        dataset_name: Name of the dataset
        dataset_id: Dataset ID
        stats: Processing statistics
        
    Returns:
        HTML email content
    """
    train_count = stats.get("train_count", 0)
    val_count = stats.get("val_count", 0)
    test_count = stats.get("test_count", 0)
    total_samples = stats.get("output_samples", train_count + val_count + test_count)
    languages = stats.get("languages", {})
    bias_score = stats.get("bias_score", 0.0)
    bias_severity = stats.get("bias_severity", "low")
    
    # Format languages
    lang_html = ""
    if languages:
        lang_items = [f"<li>{lang}: {count} samples</li>" for lang, count in languages.items()]
        lang_html = f"<ul>{''.join(lang_items)}</ul>"
    else:
        lang_html = "<p>No language data available</p>"
    
    # Bias severity color
    severity_colors = {
        "low": "#28a745",
        "medium": "#ffc107",
        "high": "#dc3545",
    }
    severity_color = severity_colors.get(bias_severity.lower(), "#6c757d")
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .success-badge {{
            background: #28a745;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            display: inline-block;
            margin-bottom: 15px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-box {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
        }}
        .bias-indicator {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        }}
        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: bold;
            margin-top: 20px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            font-size: 12px;
            color: #6c757d;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 Dataset Ready!</h1>
        <p>Your dataset has been processed successfully</p>
    </div>
    
    <div class="content">
        <span class="success-badge">✓ Processing Complete</span>
        
        <h2>Hello {user_name},</h2>
        
        <p>Great news! Your dataset <strong>"{dataset_name}"</strong> has been processed and is now ready for fine-tuning.</p>
        
        <h3>Processing Summary</h3>
        
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{train_count}</div>
                <div class="stat-label">Training</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{val_count}</div>
                <div class="stat-label">Validation</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{test_count}</div>
                <div class="stat-label">Test</div>
            </div>
        </div>
        
        <p><strong>Total Samples:</strong> {total_samples}</p>
        
        <h3>Language Distribution</h3>
        {lang_html}
        
        <h3>⚖️ Bias Analysis</h3>
        <p>
            Bias Score: <strong>{bias_score:.2f}</strong> | 
            Severity: <span class="bias-indicator" style="background: {severity_color};">{bias_severity.upper()}</span>
        </p>
        
        <h3>Next Steps</h3>
        <p>You can now start a fine-tuning job using this dataset. Visit the platform to configure your training parameters.</p>
        
        <center>
            <a href="#" class="cta-button">Start Fine-Tuning</a>
        </center>
        
        <p style="margin-top: 30px; font-size: 12px; color: #6c757d;">
            Dataset ID: {dataset_id}
        </p>
    </div>
    
    <div class="footer">
        <p>LLM Fine-Tuning Platform | Powered by MLOps</p>
        <p>This is an automated message. Please do not reply.</p>
    </div>
</body>
</html>
"""


def get_failure_email_html(
    user_name: str,
    dataset_name: str,
    dataset_id: str,
    error_message: str,
    is_admin_copy: bool = False,
) -> str:
    """
    Generate HTML email for failed dataset processing.
    
    Args:
        user_name: User's name or email
        dataset_name: Name of the dataset
        dataset_id: Dataset ID
        error_message: Error details
        is_admin_copy: Whether this is the admin notification copy
        
    Returns:
        HTML email content
    """
    admin_banner = ""
    if is_admin_copy:
        admin_banner = """
        <div style="background: #dc3545; color: white; padding: 10px; text-align: center; margin-bottom: 20px; border-radius: 5px;">
            ADMIN NOTIFICATION - User Processing Failure
        </div>
        """
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .error-badge {{
            background: #dc3545;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            display: inline-block;
            margin-bottom: 15px;
        }}
        .error-box {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-left: 4px solid #dc3545;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-family: monospace;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .help-section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: bold;
            margin-top: 20px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            font-size: 12px;
            color: #6c757d;
        }}
    </style>
</head>
<body>
    {admin_banner}
    
    <div class="header">
        <h1>Processing Failed</h1>
        <p>We encountered an issue processing your dataset</p>
    </div>
    
    <div class="content">
        <span class="error-badge">✗ Error Occurred</span>
        
        <h2>Hello {user_name},</h2>
        
        <p>Unfortunately, we were unable to process your dataset <strong>"{dataset_name}"</strong>.</p>
        
        <h3>🔍 Error Details</h3>
        <div class="error-box">{error_message}</div>
        
        <div class="help-section">
            <h3>💡 Common Solutions</h3>
            <ul>
                <li><strong>Invalid file format:</strong> Ensure your file is a valid ZIP or JSON</li>
                <li><strong>No code samples:</strong> Check that your files contain actual code</li>
                <li><strong>Encoding issues:</strong> Use UTF-8 encoding for all files</li>
                <li><strong>Empty files:</strong> Remove any empty or corrupted files</li>
            </ul>
        </div>
        
        <h3>Try Again</h3>
        <p>Please review your dataset and try uploading again. If the problem persists, contact support.</p>
        
        <center>
            <a href="#" class="cta-button">Re-upload Dataset</a>
        </center>
        
        <p style="margin-top: 30px; font-size: 12px; color: #6c757d;">
            Dataset ID: {dataset_id}<br>
            Timestamp: {datetime.utcnow().isoformat()}
        </p>
    </div>
    
    <div class="footer">
        <p>LLM Fine-Tuning Platform | Powered by MLOps</p>
        <p>Need help? Contact support at mlopsproject25@gmail.com</p>
    </div>
</body>
</html>
"""


def get_success_email_subject(dataset_name: str) -> str:
    """Get subject line for success email."""
    return f"Dataset '{dataset_name}' is Ready for Training"


def get_failure_email_subject(dataset_name: str, is_admin: bool = False) -> str:
    """Get subject line for failure email."""
    if is_admin:
        return f"[ADMIN ALERT] Dataset Processing Failed: {dataset_name}"
    return f"Dataset '{dataset_name}' Processing Failed"
