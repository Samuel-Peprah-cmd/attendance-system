import uuid
import threading
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.broadcast import Broadcast, BroadcastAttachment, BroadcastRecipient
from app.models.student import Student
from app.models.staff import Staff
from app.services.storage_helper import upload_file_to_r2

communications_bp = Blueprint("communications", __name__, url_prefix="/communications")

@communications_bp.route('/broadcast', methods=['GET'])
@login_required
def compose():
    return render_template('schools/broadcast.html')

@communications_bp.route('/broadcast/send', methods=['POST'])
@login_required
def send_broadcast():
    school_id = current_user.school_id
    
    # 1. Grab Core Data
    subject = request.form.get('subject')
    message_html = request.form.get('message_html')
    audience = request.form.get('audience')
    channels = request.form.getlist('channels') # returns ['email', 'whatsapp'] etc.

    # 2. Create the Broadcast Record
    broadcast = Broadcast(
        school_id=school_id,
        created_by_user_id=current_user.id,
        subject=subject,
        message_html=message_html,
        channel_email='email' in channels,
        channel_sms='sms' in channels,
        channel_whatsapp='whatsapp' in channels,
        target_audience=audience,
        status='queued'
    )
    db.session.add(broadcast)
    db.session.flush() # Get the broadcast.id without committing yet

    # 3. Handle Cloudflare R2 Attachments
    files = request.files.getlist('attachments')
    for file in files:
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[1].lower()
            safe_name = f"broadcasts/{broadcast.id}_{uuid.uuid4().hex[:8]}.{ext}"
            
            # Upload to R2
            file_bytes = file.read()
            file_url = upload_file_to_r2(file_bytes, safe_name, content_type=file.mimetype)
            
            if file_url:
                attachment = BroadcastAttachment(
                    broadcast_id=broadcast.id,
                    school_id=school_id,
                    original_name=file.filename,
                    file_url=file_url,
                    mime_type=file.mimetype
                )
                db.session.add(attachment)

    # 4. Resolve the Audience (Gather Recipient Contacts)
    recipients_added = 0
    if audience == 'all_parents':
        # Get unique parent emails/phones to avoid spamming siblings' parents twice
        students = Student.query.filter_by(school_id=school_id, is_active=True).all()
        processed_emails = set()
        
        for student in students:
            email = student.guardian_one_email.lower().strip() if student.guardian_one_email else None
            if email and email not in processed_emails:
                processed_emails.add(email)
                rec = BroadcastRecipient(
                    broadcast_id=broadcast.id,
                    recipient_type='guardian',
                    name=student.guardian_one_name,
                    email=email,
                    phone=student.guardian_one_phone
                )
                db.session.add(rec)
                recipients_added += 1

    elif audience == 'all_staff':
        staff_members = Staff.query.filter_by(school_id=school_id, is_active=True).all()
        for staff in staff_members:
            rec = BroadcastRecipient(
                broadcast_id=broadcast.id,
                recipient_type='staff',
                name=staff.full_name,
                email=staff.email,
                phone=staff.phone
            )
            db.session.add(rec)
            recipients_added += 1

    broadcast.total_recipients = recipients_added
    
    try:
        db.session.commit()
        
        # 5. TRIGGER THE DISPATCHER (Background Thread)
        # We use a thread here so the admin doesn't stare at a loading screen for 5 minutes!
        from app.services.broadcast_dispatcher import process_broadcast
        app_context = current_app._get_current_object()
        threading.Thread(target=process_broadcast, args=(app_context, broadcast.id)).start()
        
        flash(f"Broadcast successfully queued for {recipients_added} recipients!", "success")
        return redirect(url_for('communications.compose'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Broadcast Error: {e}")
        flash("Failed to queue broadcast. Check system logs.", "danger")
        return redirect(url_for('communications.compose'))


@communications_bp.route('/history', methods=['GET'])
@login_required
def history():
    # Fetch all broadcasts for this school, newest first
    broadcasts = Broadcast.query.filter_by(school_id=current_user.school_id).order_by(Broadcast.created_at.desc()).all()
    
    # We will pass them to the template
    return render_template('schools/broadcast_history.html', broadcasts=broadcasts)

@communications_bp.route('/analytics/<int:broadcast_id>', methods=['GET'])
@login_required
def analytics(broadcast_id):
    # Security: Ensure this school owns this broadcast
    broadcast = Broadcast.query.filter_by(id=broadcast_id, school_id=current_user.school_id).first_or_404()
    
    # Get all recipients for this specific broadcast
    recipients = BroadcastRecipient.query.filter_by(broadcast_id=broadcast.id).all()
    
    # Calculate Live Stats
    total = len(recipients)
    sent = sum(1 for r in recipients if r.status == 'sent')
    failed = sum(1 for r in recipients if r.status == 'failed')
    pending = sum(1 for r in recipients if r.status == 'pending')
    
    # Calculate delivery rate percentage
    success_rate = int((sent / total * 100)) if total > 0 else 0

    return render_template('schools/broadcast_analytics.html', 
                           broadcast=broadcast, 
                           recipients=recipients,
                           total=total, sent=sent, failed=failed, pending=pending,
                           success_rate=success_rate)