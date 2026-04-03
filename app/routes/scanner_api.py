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
from app.services.feature_gate_service import FeatureGateService

scanner_api_bp = Blueprint('scanner_api', __name__)


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
    # location_info = reverse_geocode_google(lat, lng) if (lat and lng) else {}
    
    # # 4. Geofencing Logic (STRICT FLOATING POINT VERSION)
    # is_on_campus = False
    # distance_from_school = 999999
    
    # if lat is not None and lng is not None and device.school.latitude is not None:
    #     try:
    #         user_lat = float(lat)
    #         user_lng = float(lng)
    #         school_lat = float(device.school.latitude)
    #         school_lng = float(device.school.longitude)
    #         allowed_radius = float(device.school.radius_meters or 200)

    #         # Calculate Distance
    #         distance_from_school = haversine_distance(user_lat, user_lng, school_lat, school_lng)
            
    #         # The Final Verdict
    #         is_on_campus = distance_from_school <= allowed_radius
            
    #         # Debugger
    #         print(f"📍 GEO-DEBUG | Dist: {distance_from_school:.2f}m | Allowed: {allowed_radius}m | Safe: {is_on_campus}")

    #     except ValueError as e:
    #         print(f"❌ GEO MATH ERROR: {e}")
    #         is_on_campus = False
    
    location_info = {}
    is_on_campus = True # Default to True for basic plans without geofencing
    
    # 🚨 PRODUCTION LOCK: Only run expensive GPS logic if they paid for it
    if FeatureGateService.can_use_feature(device.school_id, 'gps'):
        location_info = reverse_geocode_google(lat, lng) if (lat and lng) else {}
        
        # 4. Geofencing Logic
        if lat is not None and lng is not None and device.school.latitude is not None:
            try:
                user_lat, user_lng = float(lat), float(lng)
                school_lat, school_lng = float(device.school.latitude), float(device.school.longitude)
                allowed_radius = float(device.school.radius_meters or 200)

                distance_from_school = haversine_distance(user_lat, user_lng, school_lat, school_lng)
                is_on_campus = distance_from_school <= allowed_radius
            except ValueError as e:
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
