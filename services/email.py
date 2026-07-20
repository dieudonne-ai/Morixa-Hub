"""
services/email.py
Envoi d'emails via Resend (100 emails/jour gratuits).
Créez un compte sur https://resend.com, récupérez votre API key.
"""

import os
import requests

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL      = os.environ.get("FROM_EMAIL", "Morixa Hub <onboarding@resend.dev>")


def send_email(to_email, subject, html_body):
    """Envoie un email via l'API Resend. Retourne True/False."""
    if not RESEND_API_KEY:
        print(f"⚠️  RESEND_API_KEY manquant — email non envoyé à {to_email}")
        return False

    try:
        res = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from":    FROM_EMAIL,
                "to":      [to_email],
                "subject": subject,
                "html":    html_body,
            },
            timeout=10,
        )
        return res.status_code == 200
    except Exception as e:
        print(f"❌ Erreur envoi email : {e}")
        return False


def send_password_reset_email(to_email, full_name, reset_link):
    html = f"""
    <div style="font-family:sans-serif; max-width:480px; margin:0 auto; padding:24px;">
      <h2 style="color:#1a1a1a;">Reset your password</h2>
      <p style="color:#555; line-height:1.6;">
        Hello Dr. {full_name},<br><br>
        We received a request to reset your Morixa Hub password.
        Click the button below to choose a new one. This link expires in 1 hour.
      </p>
      <a href="{reset_link}"
         style="display:inline-block; background:#185FA5; color:#fff;
                padding:12px 24px; border-radius:8px; text-decoration:none;
                font-weight:600; margin:16px 0;">
        Reset my password
      </a>
      <p style="color:#888; font-size:13px;">
        If you didn't request this, you can safely ignore this email.
      </p>
    </div>
    """
    return send_email(to_email, "Reset your Morixa Hub password", html)


def send_welcome_email(to_email, full_name):
    html = f"""
    <div style="font-family:sans-serif; max-width:480px; margin:0 auto; padding:24px;">
      <h2 style="color:#1a1a1a;">Welcome to Morixa Hub, Dr. {full_name}</h2>
      <p style="color:#555; line-height:1.6;">
        Your account has been created. Start by publishing a clinical case,
        protocol, or exploring what your colleagues are sharing.
      </p>
      <a href="https://morixa-hub-api.onrender.com"
         style="display:inline-block; background:#185FA5; color:#fff;
                padding:12px 24px; border-radius:8px; text-decoration:none;
                font-weight:600; margin:16px 0;">
        Go to Morixa Hub
      </a>
    </div>
    """
    return send_email(to_email, "Welcome to Morixa Hub", html)
