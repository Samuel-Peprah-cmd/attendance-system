# app/services/notification_service.py
import os
from datetime import datetime
from flask import render_template, current_app, url_for
from flask_mail import Message
from app.extensions import mail
from twilio.rest import Client
from app.services.feature_gate_service import FeatureGateService

def format_to_e164(phone, school_prefix="+233"):
    """
    Cleans phone numbers and ensures they are in +CountryCode format.
    """
    if not phone: return None
    clean_phone = "".join(filter(str.isdigit, str(phone)))
    
    if clean_phone.startswith('0'):
        return school_prefix + clean_phone[1:]
    if not clean_phone.startswith('+'):
        # Check if the prefix is already there but missing the +
        if clean_phone.startswith(school_prefix.replace("+", "")):
            return "+" + clean_phone
        return school_prefix + clean_phone
    return clean_phone

def get_school_logo_url(school):
    """
    Retrieves the public Cloudflare R2 URL for the school logo.
    This replaces the old, heavy CID email attachments!
    """
    if school and school.logo_path:
        # If the path in the DB is already a full Cloudflare URL, return it
        if school.logo_path.startswith("http"):
            return school.logo_path
        
        # (Optional) Temporary fallback just in case you still have old local logos in the database
        # return f"https://your-temporary-domain.com/static/uploads/logos/{school.logo_path}"
    
    return None

def send_parent_welcome(email, temp_password, school, student=None):
    """
     Fires Email, SMS, and WhatsApp for new student enrollment.
    """
    # 1. EMAIL
    msg = Message(
        subject=f"Enrollment Confirmed: {student.full_name if student else 'New Student'}",
        recipients=[email]
    )
    
    # Grab the public Cloudflare link instead of attaching a file!
    logo_url = get_school_logo_url(school)
    
    msg.html = render_template('emails/welcome_parent.html', 
                               email=email, 
                               student=student, 
                               school=school, 
                               temp_password=temp_password, 
                               login_url=url_for('auth.login', _external=True), 
                               logo_url=logo_url)
    try:
        mail.send(msg)
    except Exception as e:
        print(f"❌ Welcome Email Failed: {e}")

    # 2. SMS/WHATSAPP
    if student and student.guardian_one_phone:
        msg_text = (
            f"Welcome to {school.name}! {student.full_name} is enrolled. "
            f"To receive WhatsApp safety alerts, please click here: "
            f"https://wa.me/{os.getenv('TWILIO_WHATSAPP_NUMBER')}?text=join%20{os.getenv('TWILIO_SANDBOX_KEYWORD')}"
        )
        _send_twilio_messages(student.guardian_one_phone, msg_text, school.name)

def send_attendance_alert(participant, status, is_delayed=False, notice=None, location=None):
    """
    Main trigger for real-time (and offline-synced) attendance alerts.
    """
    school = participant.school
    time_label = "earlier today" if is_delayed else datetime.now().strftime("%I:%M %p")
    
    # Identify if Student or Staff
    p_type = 'staff' if not hasattr(participant, 'guardian_one_email') else 'student'
    recipient = participant.email if p_type == 'staff' else participant.guardian_one_email
    recipient_phone = participant.guardian_one_phone if p_type == 'student' else participant.phone
    
    msg = Message(subject=f"[{school.name}] Security Alert", recipients=[recipient])
    
    # Grab the public Cloudflare link
    logo_url = get_school_logo_url(school)
    
    msg.html = render_template(
        'emails/attendance_alert.html',
        participant=participant,
        participant_type=p_type,
        student=participant if p_type == 'student' else None, # Compatibility for old template vars
        school=school,
        status=status,
        time=time_label,
        location=location,
        notice=notice,
        logo_url=logo_url
    )

    # try:
    #     mail.send(msg)

    #     if recipient_phone:
    #         # Short SMS for speed
    #         msg_text = f"Security: {participant.full_name} {status} at {school.name} ({time_label}). Loc: {location.get('place_name', 'Campus') if location else 'Campus'}"
    #         _send_twilio_messages(recipient_phone, msg_text, school.name)
    # except Exception as e:
    #     print(f"🚨 Notification Dispatch Failure: {e}")
    
    try:
        mail.send(msg)

        if recipient_phone:
            # 🚨 PRODUCTION LOCK: Check if SMS is enabled for this school before sending
            if FeatureGateService.can_use_feature(school.id, 'sms'):
                msg_text = f"Security: {participant.full_name} {status} at {school.name} ({time_label}). Loc: {location.get('place_name', 'Campus') if location else 'Campus'}"
                _send_twilio_messages(recipient_phone, msg_text, school.name)
                
    except Exception as e:
        print(f"🚨 Notification Dispatch Failure: {e}")


def _send_twilio_messages(to_phone, msg_text, school_name="ATOM SECURITY"):
    """
    Private helper to handle the Twilio SMS and WhatsApp dispatch.
    """
    try:
        client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        to_number = format_to_e164(to_phone)
        
        # 1. SMS Dispatch
        client.messages.create(
            body=msg_text, 
            from_=os.getenv("TWILIO_PHONE_NUMBER"), 
            to=to_number
        )
        
        # 2. WhatsApp Dispatch
        client.messages.create(
            body=f"*{school_name}*\n{msg_text}", 
            from_=f"whatsapp:{os.getenv('TWILIO_WHATSAPP_NUMBER')}", 
            to=f"whatsapp:{to_number}"
        )
        print(f"📲 TWILIO SUCCESS: SMS/WA sent to {to_number}")
    except Exception as e:
        print(f"❌ TWILIO ERROR: {e}")

def send_safety_alert(student, status):
    """
    Emergency trigger for immediate security notifications.
    """
    time_now = datetime.now().strftime("%H:%M")
    msg_body = f"URGENT: {student.full_name} safety status updated to {status} at {time_now}."

    # 1. EMAIL
    msg = Message(subject=f"EMERGENCY: {student.full_name}", recipients=[student.guardian_one_email])
    
    logo_url = get_school_logo_url(student.school)
    msg.body = msg_body
    
    if logo_url:
        msg.html = f"<div style='text-align:center;'><img src='{logo_url}' height='50'><p>{msg_body}</p></div>"
    
    try:
        mail.send(msg)
    except Exception as e:
        print(f"❌ Safety Email Failed: {e}")

    # 2. SMS/WHATSAPP
    if student.guardian_one_phone:
        _send_twilio_messages(student.guardian_one_phone, msg_body, student.school.name)
