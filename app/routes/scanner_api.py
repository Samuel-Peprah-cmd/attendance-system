import threading
from flask import Blueprint, request, jsonify, current_app, url_for
from app.models.scanner_device import ScannerDevice
from app.models.student import Student
from app.models.staff import Staff
from app.models.attendance import Attendance
from app.models.notices import SchoolNotice 
from app.extensions import db, limiter
from datetime import datetime
from app.services.notification_service import send_attendance_alert
from app.services.geocoding_service import resolve_location
from app.utils.geo import calculate_distance
from app.services.location_service import reverse_geocode_google
from math import radians, cos, sin, asin, sqrt

scanner_api_bp = Blueprint('scanner_api', __name__)

# def run_async_alert(app_instance, participant_id, p_type, direction, is_delayed=False, notice_text=None, location_data=None):
#     """
#     Handles triple-channel alerts (SMS, WhatsApp, Email) in a background thread
#     to keep the scanner UI fast and responsive.
#     """
#     with app_instance.app_context():
#         try:
#             # 1. Re-fetch participant in this thread's database session
#             if p_type == "student":
#                 participant = Student.query.get(participant_id)
#             else:
#                 participant = Staff.query.get(participant_id)

#             if participant:
#                 # 2. Trigger the notification engine with GPS and Notices
#                 send_attendance_alert(
#                     participant=participant, 
#                     status=direction, 
#                     is_delayed=is_delayed, 
#                     notice=notice_text,
#                     location=location_data
#                 )
#                 print(f"🚀 Notifications dispatched for {participant.full_name}")
#         except Exception as e:
#             print(f"🔥 Background Notification Error: {e}")

def run_async_alert(app_instance, participant_id, p_type, direction, is_delayed=False, notice_text=None, location_data=None):
    with app_instance.app_context():
        try:
            participant = Student.query.get(participant_id) if p_type == "student" else Staff.query.get(participant_id)
            if participant:
                send_attendance_alert(
                    participant=participant, 
                    status=direction, 
                    is_delayed=is_delayed, 
                    notice=notice_text,
                    location=location_data
                )
                print(f"🚀 Notifications dispatched for {participant.full_name}")
        except Exception as e:
            print(f"🔥 Background Notification Error: {e}")

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in METERS.
    """
    # Convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [float(lon1), float(lat1), float(lon2), float(lat2)])

    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers
    return c * r * 1000 # Convert to meters

# @scanner_api_bp.route('/scan', methods=['POST'])
# @limiter.limit("2 per second")
# def process_scan():
#     data = request.get_json(silent=True)
#     if not data: return jsonify({"success": False, "message": "No data"}), 400
        
#     device_key = request.headers.get('X-Device-Key')
#     qr_token = data.get('qr_token')
#     lat, lng = data.get('lat'), data.get('lng')

#     # 1. Device Security
#     device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
#     if not device: return jsonify({"success": False, "message": "Unauthorized Device"}), 401
    
#     school = device.school

#     # 2. Identity Lookup
#     p_type = "student"
#     participant = Student.query.filter_by(qr_token=qr_token, school_id=device.school_id, is_active=True).first()
#     if not participant:
#         participant = Staff.query.filter_by(qr_token=qr_token, school_id=device.school_id, is_active=True).first()
#         p_type = "staff"

#     if not participant: return jsonify({"success": False, "message": "ID Denied: User not found"}), 404
    
#     # 3. GPS Intelligence (Pulling Google Maps style info)
#     location_info = resolve_location(lat, lng) if (lat and lng) else {}
    
#     # 4. Geofencing Calculation
#     is_on_campus = calculate_distance(lat, lng, device.school.latitude, device.school.longitude) <= device.school.radius_meters if lat else True
    
#     # 4. Time Handling
#     client_time = data.get('timestamp') 
#     log_time = datetime.fromtimestamp(float(client_time)) if client_time else datetime.utcnow()

#     # 5. Direction Toggle
#     query = Attendance.query.filter_by(school_id=device.school_id, participant_type=p_type)
#     query = query.filter_by(student_id=participant.id) if p_type == "student" else query.filter_by(staff_id=participant.id)
#     last_log = query.order_by(Attendance.timestamp.desc()).first()
#     direction = "OUT" if (last_log and last_log.status == "IN") else "IN"

#     # 6. Save Log (Uses 'latitude' - Ensure you ran the migration for the typo fix!)
#     new_log = Attendance(
#         school_id=device.school_id,
#         student_id=participant.id if p_type == "student" else None,
#         staff_id=participant.id if p_type == "staff" else None,
#         participant_type=p_type,
#         status=direction,
#         timestamp=log_time,
#         latitude=lat,
#         longitude=lng,
#         is_within_boundary=is_on_campus,
#         place_name=location_info.get('place_name', "Verified Campus"),
#         country=location_info.get('country'),
#         city=location_info.get('city'),
#         town=location_info.get('town'),
#         street=location_info.get('street')
#     )
#     db.session.add(new_log)
#     device.update_last_seen() 
#     db.session.commit()

#     # 7. Asynchronous Alerts (restored to use HTML Template)
#     active_notice = SchoolNotice.query.filter_by(school_id=device.school_id, is_active=True).order_by(SchoolNotice.created_at.desc()).first()
#     notice_text = active_notice.content if active_notice else None
    
#     # 7. PREPARE IMAGE URL (The fix for the image not showing)
#     folder = 'students' if p_type == 'student' else 'staff'
#     # Generates: http://your-ip:5000/static/uploads/staff/filename.jpg
#     photo_url = url_for('static', filename=f'uploads/{folder}/{participant.photo_path}', _external=True)
    
#     flask_app = current_app._get_current_object()
#     threading.Thread(target=run_async_alert, args=(flask_app, participant.id, p_type, direction, bool(client_time), notice_text, location_info)).start()

#     # 8. Success Response for UI
#     return jsonify({
#         "success": True,
#         "name": participant.full_name,          # Key for UI label
#         "full_name": participant.full_name,     # Redundant key for safety
#         "student_code": participant.student_code if p_type == "student" else participant.staff_code,
#         "on_campus": is_on_campus,
#         "type": p_type,
#         "class": participant.classroom.name if (p_type == "student" and hasattr(participant, 'classroom') and participant.classroom) else "Staff Member",
#         "direction": direction,
#         "photo": photo_url,
#         "notice": notice_text,
#         "timestamp": log_time.strftime("%I:%M %p")
#     }), 200

# @scanner_api_bp.route('/scan', methods=['POST'])
# @limiter.limit("2 per second")
# def process_scan():
#     data = request.get_json(silent=True)
#     device_key = request.headers.get('X-Device-Key')
#     qr_token = data.get('qr_token')
#     lat, lng = data.get('lat'), data.get('lng')

#     # 1. Device Security
#     device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
#     if not device: return jsonify({"success": False, "message": "Unauthorized Device"}), 401
    
#     # 2. Universal Identity Lookup (Student or Staff)
#     p_type = "student"
#     participant = Student.query.filter_by(qr_token=qr_token, school_id=device.school_id).first()
    
#     if not participant:
#         participant = Staff.query.filter_by(qr_token=qr_token, school_id=device.school_id).first()
#         p_type = "staff"

#     if not participant: 
#         return jsonify({"success": False, "message": "Access Denied: User Not Found"}), 404
    
#     # 3. GPS Intelligence
#     location_info = resolve_location(lat, lng) if (lat and lng) else {}
#     is_on_campus = calculate_distance(lat, lng, device.school.latitude, device.school.longitude) <= device.school.radius_meters if lat else True

#     # 4. Save Attendance Log
#     query = Attendance.query.filter_by(school_id=device.school_id, participant_type=p_type)
#     query = query.filter_by(student_id=participant.id) if p_type == "student" else query.filter_by(staff_id=participant.id)
#     last_log = query.order_by(Attendance.timestamp.desc()).first()
#     direction = "OUT" if (last_log and last_log.status == "IN") else "IN"

#     log_time = datetime.utcnow()
#     new_log = Attendance(
#         school_id=device.school_id,
#         student_id=participant.id if p_type == "student" else None,
#         staff_id=participant.id if p_type == "staff" else None,
#         participant_type=p_type,
#         status=direction,
#         timestamp=log_time,
#         latitude=lat,
#         longitude=lng,
#         is_within_boundary=is_on_campus,
#         place_name=location_info.get('place_name', "Verified Campus Zone")
#     )
#     db.session.add(new_log)
#     db.session.commit()

#     folder = 'students' if p_type == 'student' else 'staff'
#     filename = participant.photo_path or 'default.png'
    
#     # 🚩 THE FIX: Generate an absolute URL that points to the BACKEND (Port 5000)
#     # This ensures that an app on Port 5001 can see the file on Port 5000.
#     absolute_image_url = url_for('static', filename=f'uploads/{folder}/{filename}', _external=True)

#     # 6. Resolve Designation/Class safely
#     if p_type == "student":
#         designation = participant.classroom.name if participant.classroom else "No Class"
#         id_code = participant.student_code
#     else:
#         designation = participant.designation or "Official Staff"
#         id_code = participant.staff_code

#     # 7. Dispath Background Notifications
#     active_notice = SchoolNotice.query.filter_by(school_id=device.school_id, is_active=True).first()
#     flask_app = current_app._get_current_object()
#     threading.Thread(target=run_async_alert, args=(
#         flask_app, participant.id, p_type, direction, False, 
#         active_notice.content if active_notice else None, location_info
#     )).start()

#     # 8. THE MASTER RESPONSE (Standardized keys for all scanners)
#     return jsonify({
#         "success": True,
#         "name": participant.full_name,        # Kivy often uses 'name'
#         "full_name": participant.full_name,   # Web often uses 'full_name'
#         "student_code": id_code,              # Kivy UI lookups
#         "staff_code": id_code,                # Kivy UI lookups
#         "type": p_type,
#         "class": designation,                 # Student Class or Staff Designation
#         "designation": designation,           # Backup for Staff UI
#         "direction": direction,
#         "on_campus": is_on_campus,
#         "photo_url": absolute_image_url,
#         "timestamp": log_time.strftime("%I:%M %p"),
#         "notice": active_notice.content if active_notice else None
#     }), 200

@scanner_api_bp.route('/scan', methods=['POST'])
@limiter.limit("2 per second")
def process_scan():
    data = request.get_json(silent=True) or {}
    device_key = request.headers.get('X-Device-Key')
    qr_token = data.get('qr_token')
    lat, lng = data.get('lat'), data.get('lng')
    
    # 1. Secure Device Handshake
    device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
    if not device: 
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    # 2. Universal Identity Resolve
    participant = Student.query.filter_by(qr_token=qr_token, school_id=device.school_id).first()
    p_type = "student"
    
    if not participant:
        participant = Staff.query.filter_by(qr_token=qr_token, school_id=device.school_id).first()
        p_type = "staff"

    # 🛑 THE GATEKEEPER CHECK: Stop here if they don't exist
    if not participant: 
        return jsonify({"success": False, "message": "ID Not Recognized"}), 404
    
    # Check if deactivated
    if hasattr(participant, 'is_active') and not participant.is_active:
        return jsonify({
            "success": False, 
            "message": "CARD DEACTIVATED",
            "name": participant.full_name
        }), 403 

    # 🚩 Identity Metadata Logic
    if p_type == "student":
        if hasattr(participant, 'student_class') and participant.student_class:
            display_info = f"Class: {participant.student_class.name}"
        else:
            display_info = "Student (Unassigned)"
    else:
        display_info = participant.designation or "Staff Member"
    
    # 3. GPS Intelligence (Google Maps Resolution)
    location_info = reverse_geocode_google(lat, lng) if (lat and lng) else {}
    
    # 4. Geofencing Logic (STRICT FLOATING POINT VERSION)
    is_on_campus = False
    distance_from_school = 999999
    
    if lat is not None and lng is not None and device.school.latitude is not None:
        try:
            user_lat = float(lat)
            user_lng = float(lng)
            school_lat = float(device.school.latitude)
            school_lng = float(device.school.longitude)
            allowed_radius = float(device.school.radius_meters or 200)

            # Calculate Distance
            distance_from_school = haversine_distance(user_lat, user_lng, school_lat, school_lng)
            
            # The Final Verdict
            is_on_campus = distance_from_school <= allowed_radius
            
            # Debugger
            print(f"📍 GEO-DEBUG | Dist: {distance_from_school:.2f}m | Allowed: {allowed_radius}m | Safe: {is_on_campus}")

        except ValueError as e:
            print(f"❌ GEO MATH ERROR: {e}")
            is_on_campus = False
    else:
        print(f"⚠️ GEO WARNING: Missing GPS Data! Lat: {lat}, Lng: {lng}")
        is_on_campus = False

    # 5. Smart Direction Toggle (IN vs OUT) with Anti-Double-Scan
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if p_type == "student":
        last_log = Attendance.query.filter(
            Attendance.school_id == device.school_id,
            Attendance.student_id == participant.id,
            Attendance.timestamp >= today_start
        ).order_by(Attendance.timestamp.desc()).first()
    else:
        last_log = Attendance.query.filter(
            Attendance.school_id == device.school_id,
            Attendance.staff_id == participant.id,
            Attendance.timestamp >= today_start
        ).order_by(Attendance.timestamp.desc()).first()

    # Logic: Toggle IN / OUT
    if not last_log:
        direction = "IN"
    else:
        # 🛡️ ANTI-DOUBLE-SCAN COOLDOWN (5 minutes)
        time_since_last = (datetime.utcnow() - last_log.timestamp).total_seconds()
        if time_since_last < 300:  
            # Keep the same direction if they scan again too fast
            direction = last_log.status 
        else:
            # Normal toggle
            direction = "IN" if last_log.status == "OUT" else "OUT"

    # 6. Save High-Intelligence Log
    log_time = datetime.utcnow()
    punctuality = "ON TIME" 
    
    # Calculate Lateness
    # Note: Using log_time.time() ensures we are comparing UTC to UTC correctly if needed
    if direction == "IN" and device.school and device.school.opening_time:
        if log_time.time() > device.school.opening_time:
            punctuality = "LATE"

    new_log = Attendance(
        school_id=device.school_id,
        student_id=participant.id if p_type == "student" else None,
        staff_id=participant.id if p_type == "staff" else None,
        participant_type=p_type,
        status=direction,
        remarks=punctuality,
        timestamp=log_time,
        latitude=lat,
        longitude=lng,
        is_within_boundary=is_on_campus,
        place_name=location_info.get('place_name', "Verified Campus"),
        street=location_info.get('street'),
        town=location_info.get('town'),
        city=location_info.get('city'),
        country=location_info.get('country')
    )
    db.session.add(new_log)
    db.session.commit()

    # 7. Response Construction
    # photo_folder = 'students' if p_type == 'student' else 'staff'
    # photo_url = url_for('static', filename=f'uploads/{photo_folder}/{participant.photo_path}', _external=True)

    photo_url = participant.photo_path
    
    # LEGACY FALLBACK: If the photo doesn't start with 'http', it's an old local file!
    if photo_url and not photo_url.startswith("http"):
        photo_folder = 'students' if p_type == 'student' else 'staff'
        photo_url = url_for('static', filename=f'uploads/{photo_folder}/{photo_url}', _external=True)

    # 8. Notification Dispatch
    flask_app = current_app._get_current_object()
    
    threading.Thread(target=run_async_alert, args=(
        flask_app,           
        participant.id,      
        p_type,              
        direction,           
        is_on_campus,        
        None,                
        location_info        
    )).start()

    return jsonify({
        "success": True,
        "name": participant.full_name,
        "display_info": display_info,  
        "type": p_type,
        "id": participant.student_code if p_type == "student" else participant.staff_code,
        "direction": direction,
        "punctuality": punctuality, 
        "on_campus": is_on_campus,
        "location": location_info.get('place_name', "Verified Campus"),
        "photo_url": photo_url,
        "timestamp": log_time.strftime("%I:%M %p"),
        "status": "SUCCESS" if is_on_campus else "BREACH"
    }), 200

@scanner_api_bp.route('/ping', methods=['GET'])
def ping():
    """Device heartbeat to show 'Online' status in dashboard"""
    device_key = request.headers.get('X-Device-Key')
    if not device_key:
        return jsonify({"success": False, "message": "No key"}), 400
    device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
    if device:
        return jsonify({
            "status": "online", 
            "school": device.school.name,
            "device_name": device.device_name
        }), 200
    return jsonify({"success": False}), 401

@scanner_api_bp.route('/twilio/incoming', methods=['POST'])
def twilio_incoming():
    """Receiver for incoming parent SMS/WhatsApp messages"""
    sender = request.values.get('From')
    message_body = request.values.get('Body')
    print(f"📩 Incoming message from {sender}: {message_body}")
    return "<Response></Response>", 200 

@scanner_api_bp.route('/twilio/status', methods=['POST'])
def twilio_status():
    """Web-hook to track message delivery status"""
    message_sid = request.values.get('MessageSid')
    status = request.values.get('MessageStatus')
    print(f"📊 Message {message_sid} status update: {status}")
    return "", 200








# # app/routes/scanner_api.py
# import threading
# from flask import Blueprint, request, jsonify, current_app
# from app.models.scanner_device import ScannerDevice
# from app.models.student import Student
# from app.models.staff import Staff
# from app.models.attendance import Attendance
# from app.models.notices import SchoolNotice 
# from app.extensions import db, limiter
# from datetime import datetime
# from app.services.notification_service import send_attendance_alert
# from app.services.geocoding_service import resolve_location

# scanner_api_bp = Blueprint('scanner_api', __name__)

# def run_async_alert(app_instance, participant_id, p_type, direction, is_delayed=False, notice_text=None):
#     """
#     Handles triple-channel alerts in a separate thread.
#     Works for both Students and Staff members.
#     """
#     with app_instance.app_context():
#         try:
#             # Re-fetch the participant based on type
#             participant = None
#             if p_type == "student":
#                 participant = Student.query.get(participant_id)
#             else:
#                 participant = Staff.query.get(participant_id)

#             if participant:
#                 # master notification trigger including the active school notice
#                 send_attendance_alert(participant, direction, is_delayed=is_delayed, notice=notice_text)
#                 print(f"🚀 Notifications synced for {participant.full_name} ({p_type})")
#         except Exception as e:
#             print(f"🔥 Background Notification Error: {e}")

# @scanner_api_bp.route('/scan', methods=['POST'])
# @limiter.limit("2 per second")
# def process_scan():
#     data = request.get_json(silent=True)
#     if not data:
#         return jsonify({"success": False, "message": "No data received"}), 400
        
#     device_key = request.headers.get('X-Device-Key')
#     qr_token = data.get('qr_token')
    
#     # 📍 Capture GPS from hardware payload
#     lat = data.get('lat')
#     lng = data.get('lng')

#     # 1. Validate Device
#     device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
#     if not device:
#         return jsonify({"success": False, "message": "Unauthorized Device"}), 401

#     # 2. DUAL LOOKUP: Identify if Student or Staff
#     p_type = "student"
#     participant = Student.query.filter_by(qr_token=qr_token, school_id=device.school_id, is_active=True).first()

#     if not participant:
#         participant = Staff.query.filter_by(qr_token=qr_token, school_id=device.school_id, is_active=True).first()
#         p_type = "staff"

#     if not participant:
#         return jsonify({"success": False, "message": "ID Denied: Participant not found"}), 404
    
#     # 🕒 OFFLINE RESILIENCE: Handle client-side timestamps
#     client_time = data.get('timestamp') 
#     is_delayed = False
#     if client_time:
#         log_time = datetime.fromtimestamp(float(client_time))
#         is_delayed = True
#     else:
#         log_time = datetime.now()

#     # 🌍 SMART GPS: Resolve coordinates to Street/Town
#     location_info = {}
#     if lat and lng:
#         location_info = resolve_location(lat, lng)

#     # 📣 NOTICE BOARD: Fetch latest active notice for this school
#     active_notice = SchoolNotice.query.filter_by(
#         school_id=device.school_id, 
#         is_active=True
#     ).order_by(SchoolNotice.created_at.desc()).first()
    
#     notice_text = active_notice.content if active_notice else None

#     # 3. Toggle Logic (In/Out)
#     # Check last log for this specific participant and type
#     query = Attendance.query.filter_by(school_id=device.school_id, participant_type=p_type)
#     if p_type == "student":
#         query = query.filter_by(student_id=participant.id)
#     else:
#         query = query.filter_by(staff_id=participant.id)
    
#     last_log = query.order_by(Attendance.timestamp.desc()).first()
#     direction = "OUT" if (last_log and last_log.status == "IN") else "IN"

#     # 4. Save High-Intelligence Attendance Log
#     new_log = Attendance(
#         school_id=device.school_id,
#         student_id=participant.id if p_type == "student" else None,
#         staff_id=participant.id if p_type == "staff" else None,
#         participant_type=p_type,
#         status=direction,
#         timestamp=log_time,
#         latitude=lat,
#         longitude=lng,
#         country=location_info.get('country'),
#         city=location_info.get('city'),
#         town=location_info.get('town'),
#         street=location_info.get('street'),
#         place_name=location_info.get('place_name')
#     )
#     db.session.add(new_log)
#     device.update_last_seen() 
#     db.session.commit()

#     # 5. ASYNCHRONOUS NOTIFICATIONS (Triple-Channel)
#     flask_app = current_app._get_current_object()
#     threading.Thread(
#         target=run_async_alert, 
#         args=(flask_app, participant.id, p_type, direction, is_delayed, notice_text)
#     ).start()

#     # 6. UNIVERSAL RESPONSE
#     return jsonify({
#         "success": True,
#         "name": participant.full_name,
#         "type": p_type,
#         "designation": participant.designation if p_type == "staff" else (participant.classroom.name if participant.classroom else "General"),
#         "direction": direction,
#         "photo": participant.photo_path,
#         "location": location_info.get('place_name') or location_info.get('street') or "Verified Campus",
#         "notice": notice_text,
#         "timestamp": log_time.strftime("%I:%M %p")
#     }), 200

# @scanner_api_bp.route('/ping', methods=['GET'])
# def ping():
#     device_key = request.headers.get('X-Device-Key')
#     if not device_key:
#         return jsonify({"success": False, "message": "No key provided"}), 400
#     device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
#     if device:
#         return jsonify({
#             "status": "online", 
#             "school": device.school.name,
#             "device_name": device.device_name
#         }), 200
#     return jsonify({"success": False}), 401

# @scanner_api_bp.route('/twilio/incoming', methods=['POST'])
# def twilio_incoming():
#     sender = request.values.get('From')
#     message_body = request.values.get('Body')
#     print(f"📩 Incoming message from {sender}: {message_body}")
#     return "<Response></Response>", 200 

# @scanner_api_bp.route('/twilio/status', methods=['POST'])
# def twilio_status():
#     message_sid = request.values.get('MessageSid')
#     status = request.values.get('MessageStatus')
#     print(f"📊 Message {message_sid} status update: {status}")
#     return "", 200








# # app/routes/scanner_api.py
# import threading
# from flask import Blueprint, request, jsonify, current_app
# from app.models.scanner_device import ScannerDevice
# from app.models.student import Student
# from app.models.attendance import Attendance
# from app.extensions import db, limiter
# from datetime import datetime
# from app.services.notification_service import send_attendance_alert
# from app.services.geocoding_service import resolve_location

# scanner_api_bp = Blueprint('scanner_api', __name__)

# def run_async_alert(app_instance, student_id, direction, is_delayed=False):
#     """
#     Handles the triple-channel alert (Email, SMS, WA) in a separate thread.
#     is_delayed is True if the scan was stored offline and synced later.
#     """
#     with app_instance.app_context():
#         try:
#             # Re-fetch the student in this thread's context for database safety
#             student = Student.query.get(student_id)
#             if student:
#                 # Trigger the master notification service
#                 send_attendance_alert(student, direction, is_delayed=is_delayed)
#                 print(f"📧 Async Notifications (Triple-Channel) sent for {student.full_name}")
#         except Exception as e:
#             print(f"🔥 Background Notification Error: {e}")

# @scanner_api_bp.route('/scan', methods=['POST'])
# @limiter.limit("1 per second")
# def process_scan():
#     data = request.get_json(silent=True)
#     if not data:
#         return jsonify({"success": False, "message": "No JSON data received"}), 400
        
#     device_key = request.headers.get('X-Device-Key')
#     qr_token = data.get('qr_token')
#     lat = data.get('lat')
#     lng = data.get('lng')
    
#     # 1. Validate Device
#     device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
#     if not device:
#         return jsonify({"success": False, "message": "Unauthorized Device"}), 401

#     # 2. Validate Student (Must match the scanner's assigned school)
#     student = Student.query.filter_by(
#         qr_token=qr_token, 
#         school_id=device.school_id, 
#         is_active=True
#     ).first()

#     if not student:
#         return jsonify({"success": False, "message": "ID Denied: Student not found at this school"}), 404
    
#     # 🕒 OFFLINE RESILIENCE: Check for client-side timestamp
#     client_time = data.get('timestamp') 
#     is_delayed = False
    
#     if client_time:
#         # Client provided a time (Offline Sync mode)
#         log_time = datetime.fromtimestamp(float(client_time))
#         is_delayed = True
#     else:
#         # Real-time scan
#         log_time = datetime.now()

#     # 3. Toggle Logic (In/Out)
#     last_log = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.timestamp.desc()).first()
#     direction = "OUT" if (last_log and last_log.status == "IN") else "IN"

#     # 4. Save Attendance Log
#     new_log = Attendance(
#         student_id=student.id, 
#         school_id=device.school_id, 
#         status=direction,
#         timestamp=log_time
#     )
#     db.session.add(new_log)
#     device.update_last_seen() 
#     db.session.commit()

#     # 5. ASYNCHRONOUS NOTIFICATIONS (Email + SMS + WhatsApp) 🚀
#     # Pass the app object and is_delayed flag to the background thread
#     flask_app = current_app._get_current_object()
#     alert_thread = threading.Thread(
#         target=run_async_alert, 
#         args=(flask_app, student.id, direction, is_delayed)
#     )
#     alert_thread.start()

#     # 6. UNIVERSAL RESPONSE (Supports Kivy Tablet & Web Dashboard Scanner)
#     return jsonify({
#         "success": True,
#         "name": student.full_name,
#         "student_code": student.student_code,   # Required for Kivy Result Screen
#         "class": student.classroom.name if student.classroom else "General",
#         "direction": direction,
#         "photo": student.photo_path,             # Required for Kivy Image rendering
#         "photo_url": student.photo_path,         # Compatibility for Web Scanner
#         "timestamp": log_time.strftime("%I:%M %p")
#     }), 200

# @scanner_api_bp.route('/ping', methods=['GET'])
# def ping():
#     try:
#         device_key = request.headers.get('X-Device-Key')
#         if not device_key:
#             return jsonify({"success": False, "message": "No key provided"}), 400

#         device = ScannerDevice.query.filter_by(api_key=device_key, is_active=True).first()
        
#         if device:
#             return jsonify({
#                 "status": "online", 
#                 "school": device.school.name if device.school else "Unknown School",
#                 "device_name": device.device_name
#             }), 200
            
#         return jsonify({"success": False, "message": "Invalid Device Key"}), 401
        
#     except Exception as e:
#         print(f"🔥 PING CRASH: {str(e)}")
#         return jsonify({"success": False, "message": "Server error during ping"}), 500
    
# @scanner_api_bp.route('/twilio/incoming', methods=['POST'])
# def twilio_incoming():
#     """Handles messages sent FROM parents TO the system"""
#     sender = request.values.get('From')
#     message_body = request.values.get('Body')
    
#     print(f"📩 Incoming message from {sender}: {message_body}")
    
#     # You could add logic here to auto-reply to parents
#     return "<Response></Response>", 200 # Twilio expects a TwiML response

# @scanner_api_bp.route('/twilio/status', methods=['POST'])
# def twilio_status():
#     """Tracks if the message was Sent, Delivered, or Failed"""
#     message_sid = request.values.get('MessageSid')
#     status = request.values.get('MessageStatus')
    
#     print(f"📊 Message {message_sid} status update: {status}")
    
#     return "", 200
