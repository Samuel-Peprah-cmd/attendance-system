import os
import re
from flask_mail import Message
from twilio.rest import Client
from app.extensions import db, mail
from flask import render_template
from app.models.school import School
from app.services.notification_service import get_school_logo_url
from app.models.broadcast import Broadcast, BroadcastRecipient, BroadcastAttachment
from app.services.notification_service import format_to_e164 # Reuse your existing phone formatter

def strip_html_tags(text):
    """A simple regex to strip HTML tags for SMS/WhatsApp plain text."""
    clean = re.compile('<.*?>')
    # Replace <br> and </p> with newlines before stripping to preserve formatting
    text = text.replace('<br>', '\n').replace('</p>', '\n\n')
    return re.sub(clean, '', text).strip()

def process_broadcast(app, broadcast_id):
    """
    Runs in a background thread. Loops through recipients and sends messages.
    """
    with app.app_context():
        # 1. Fetch the broadcast and all its data
        broadcast = Broadcast.query.get(broadcast_id)
        if not broadcast:
            return

        broadcast.status = 'sending'
        db.session.commit()

        recipients = BroadcastRecipient.query.filter_by(broadcast_id=broadcast_id).all()
        attachments = BroadcastAttachment.query.filter_by(broadcast_id=broadcast_id).all()
        
        # Grab school and logo for the branded email template
        school = School.query.get(broadcast.school_id)
        logo_url = get_school_logo_url(school)

        # 2. Prepare the payloads
        # --- NEW BRANDED HTML EMAIL ---
        email_html = render_template(
            'emails/broadcast_email.html',
            school=school,
            logo_url=logo_url,
            subject=broadcast.subject,
            message_body=broadcast.message_html,
            attachments=attachments,
            cf_prefix=app.config.get('CF_PUBLIC_URL_PREFIX')
        )

        # --- SMS/WhatsApp (Plain Text + Links) ---
        plain_text = strip_html_tags(broadcast.message_html)
        if attachments:
            plain_text += "\n\nAttachments:\n"
            for att in attachments:
                file_url = att.file_url if att.file_url.startswith('http') else f"{app.config.get('CF_PUBLIC_URL_PREFIX')}/{att.file_url}"
                plain_text += f"- {att.original_name}: {file_url}\n"

        # 3. Setup Twilio Client if needed
        twilio_client = None
        if broadcast.channel_sms or broadcast.channel_whatsapp:
            try:
                twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
            except Exception as e:
                print(f"Failed to init Twilio for broadcast: {e}")

        # 4. Loop and Dispatch
        for rec in recipients:
            # --- EMAIL ---
            if broadcast.channel_email and rec.email:
                try:
                    msg = Message(
                        subject=broadcast.subject,
                        recipients=[rec.email],
                        html=email_html
                    )
                    mail.send(msg)
                    rec.status = 'sent'
                except Exception as e:
                    print(f"Broadcast Email Failed to {rec.email}: {e}")
                    rec.status = 'failed'

            # --- SMS / WHATSAPP ---
            if twilio_client and rec.phone:
                to_number = format_to_e164(rec.phone)
                
                # Send SMS
                if broadcast.channel_sms:
                    try:
                        twilio_client.messages.create(
                            body=plain_text,
                            from_=os.getenv("TWILIO_PHONE_NUMBER"),
                            to=to_number
                        )
                        rec.status = 'sent'
                    except Exception as e:
                        print(f"Broadcast SMS Failed to {to_number}: {e}")
                        rec.status = 'failed'

                # Send WhatsApp
                if broadcast.channel_whatsapp:
                    try:
                        twilio_client.messages.create(
                            body=plain_text,
                            from_=f"whatsapp:{os.getenv('TWILIO_WHATSAPP_NUMBER')}",
                            to=f"whatsapp:{to_number}"
                        )
                        rec.status = 'sent'
                    except Exception as e:
                        print(f"Broadcast WA Failed to {to_number}: {e}")
                        rec.status = 'failed'

            # Commit periodically to save status
            db.session.commit()

        # 5. Mark Complete
        broadcast.status = 'completed'
        db.session.commit()
        print(f"🚀 Broadcast {broadcast.id} completed successfully!")