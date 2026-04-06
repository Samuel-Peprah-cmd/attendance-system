#routes/biometric.py
import json
from datetime import datetime
from flask import Blueprint, request, session, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from base64 import urlsafe_b64decode
from app.models.user import User, UserPasskey
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    options_to_json,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

biometric_bp = Blueprint('biometric', __name__)

def b64url_to_hex(value: str) -> str:
    padding = '=' * (-len(value) % 4)
    return urlsafe_b64decode(value + padding).hex()

def get_rp_id():
    return request.host.split(':')[0]


def get_origin():
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    return f"{scheme}://{request.host}"

@biometric_bp.route('/register-options', methods=['POST'])
@login_required
def get_register_options():
    existing_credentials = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=bytes.fromhex(p.credential_id)
        )
        for p in current_user.passkeys.filter_by(is_active=True).all()
    ]

    options = generate_registration_options(
        rp_id=get_rp_id(),
        rp_name="ATOM Gate Security",
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.email,
        exclude_credentials=existing_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )

    session['biometric_challenge'] = options.challenge
    session['biometric_register_user_id'] = current_user.id
    return options_to_json(options)


@biometric_bp.route('/register-verify', methods=['POST'])
@login_required
def verify_registration():
    credential = request.get_json()

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=session.get('biometric_challenge'),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            require_user_verification=True,
        )

        transports = credential.get("response", {}).get("transports", [])
        passkey = UserPasskey(
            user_id=current_user.id,
            credential_id=verification.credential_id.hex(),
            public_key=verification.credential_public_key.hex(),
            sign_count=verification.sign_count,
            transports=json.dumps(transports) if transports else None,
            device_name="Saved Passkey",
            is_active=True,
        )
        db.session.add(passkey)
        db.session.commit()

        session.pop('biometric_challenge', None)
        session.pop('biometric_register_user_id', None)

        return jsonify({"success": True, "message": "Passkey saved successfully."})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@biometric_bp.route('/terminal/authenticate-options', methods=['POST'])
def terminal_auth_options():
    data = request.get_json(silent=True) or {}
    school_id = data.get("school_id")

    if not school_id:
        return jsonify({"success": False, "message": "Missing school ID."}), 400

    user = (
        User.query
        .filter_by(school_id=school_id, role='school_admin')
        .first()
    )

    if not user:
        return jsonify({"success": False, "message": "No admin found for this school."}), 404
    
    has_passkey = (
        UserPasskey.query
        .join(User, User.id == UserPasskey.user_id)
        .filter(
            User.school_id == school_id,
            UserPasskey.is_active == True
        )
        .first()
    )

    if not has_passkey:
        return jsonify({"success": False, "message": "No saved passkey found for this school."}), 404

    options = generate_authentication_options(
        rp_id=get_rp_id(),
        allow_credentials=[],  # discoverable passkey flow
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    session['biometric_challenge'] = options.challenge
    session['terminal_school_id'] = school_id

    return options_to_json(options)

@biometric_bp.route('/terminal/authenticate-verify', methods=['POST'])
def terminal_auth_verify():
    credential = request.get_json(silent=True) or {}

    try:
        credential_id_b64 = credential.get("id") or credential.get("rawId")
        if not credential_id_b64:
            return jsonify({"success": False, "message": "Missing credential id."}), 400

        credential_id_hex = b64url_to_hex(credential_id_b64)

        passkey = UserPasskey.query.filter_by(
            credential_id=credential_id_hex,
            is_active=True
        ).first()

        if not passkey:
            return jsonify({"success": False, "message": "Passkey not recognized."}), 404
        
        expected_school_id = session.get('terminal_school_id')
        if not expected_school_id:
            return jsonify({"success": False, "message": "Missing terminal school session."}), 400

        if str(passkey.user.school_id) != str(expected_school_id):
            return jsonify({"success": False, "message": "Passkey does not belong to this school."}), 403

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=session.get('biometric_challenge'),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            credential_public_key=bytes.fromhex(passkey.public_key),
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )

        passkey.sign_count = verification.new_sign_count
        passkey.last_used_at = datetime.utcnow()
        db.session.commit()

        session['scanner_unlocked'] = True
        session['scanner_unlocked_user_id'] = passkey.user_id
        
        session.pop('biometric_challenge', None)
        session.pop('terminal_school_id', None)

        return jsonify({
            "success": True,
            "message": "Terminal unlocked successfully."
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@biometric_bp.route('/reset-passkeys', methods=['POST'])
@login_required
def reset_passkeys():
    UserPasskey.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"success": True, "message": "All saved passkeys removed."})








# # app/routes/biometric.py
# import json
# from flask import Blueprint, request, session, jsonify
# from flask_login import login_required, current_user
# from app.extensions import db
# from webauthn.helpers.structs import PublicKeyCredentialDescriptor
# from webauthn import generate_registration_options, verify_registration_response, options_to_json
# from webauthn.helpers.structs import PublicKeyCredentialDescriptor, PublicKeyCredentialType, AuthenticatorSelectionCriteria, UserVerificationRequirement
# from webauthn import generate_authentication_options, verify_authentication_response

# biometric_bp = Blueprint('biometric', __name__)

# def get_rp_id():
#     # WebAuthn strictly requires the domain name without ports or schemes
#     return request.host.split(':')[0]

# def get_origin():
#     # WebAuthn strictly requires the exact scheme and hostname
#     scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
#     return f"{scheme}://{request.host}"

# @biometric_bp.route('/register-options', methods=['POST'])
# @login_required
# def get_register_options():
#     """Step 1: Server creates a cryptographic challenge for the tablet/laptop"""
#     options = generate_registration_options(
#         rp_id=get_rp_id(),
#         rp_name="ATOM Gate Security",
#         user_id=str(current_user.id).encode(), # Must be encoded to bytes
#         user_name=current_user.email,
#         authenticator_selection=AuthenticatorSelectionCriteria(
#             user_verification=UserVerificationRequirement.PREFERRED
#         )
#     )
    
#     # Save the challenge in the session so we can verify it in Step 2
#     session['biometric_challenge'] = options.challenge
    
#     # Convert the Python object into perfect JSON for the browser
#     return options_to_json(options)

# @biometric_bp.route('/register-verify', methods=['POST'])
# @login_required
# def verify_registration():
#     """Step 2: Browser sends the fingerprint signature back to be verified"""
#     credential = request.get_json()
    
#     try:
#         verification = verify_registration_response(
#             credential=credential,
#             expected_challenge=session.get('biometric_challenge'),
#             expected_origin=get_origin(),
#             expected_rp_id=get_rp_id(),
#             require_user_verification=False
#         )
        
#         # 🟢 SUCCESS! Save the public keys to the database
#         current_user.webauthn_id = verification.credential_id.hex()
#         current_user.webauthn_public_key = verification.credential_public_key.hex()
#         current_user.webauthn_sign_count = verification.sign_count
#         db.session.commit()
        
#         return jsonify({"success": True, "message": "Biometric device registered successfully!"})
        
#     except Exception as e:
#         print(f"Biometric Error: {e}")
#         return jsonify({"success": False, "message": str(e)}), 400

# # @biometric_bp.route('/authenticate-options', methods=['POST'])
# # @login_required
# # def get_auth_options():
# #     """Step 1: Ask the device to prove it has the matching fingerprint"""
# #     if not current_user.webauthn_id:
# #         return jsonify({"success": False, "message": "No biometrics registered."}), 400
        
# #     options = generate_authentication_options(
# #         rp_id=get_rp_id(),
# #         allow_credentials=[{
# #             "type": "public-key",
# #             "id": bytes.fromhex(current_user.webauthn_id)
# #         }],
# #         user_verification=UserVerificationRequirement.PREFERRED
# #     )
    
# #     session['biometric_challenge'] = options.challenge
# #     return options_to_json(options)

# @biometric_bp.route('/authenticate-options', methods=['POST'])
# @login_required
# def get_auth_options():
#     """Step 1: Ask the device to prove it has the matching fingerprint"""
#     if not current_user.webauthn_id:
#         return jsonify({"success": False, "message": "No biometrics registered."}), 400
        
#     options = generate_authentication_options(
#         rp_id=get_rp_id(),
#         allow_credentials=[PublicKeyCredentialDescriptor(
#             type=PublicKeyCredentialType.PUBLIC_KEY, # 🚨 FIX: Using the official Enum instead of a string!
#             id=bytes.fromhex(current_user.webauthn_id)
#         )],
#         user_verification=UserVerificationRequirement.PREFERRED
#     )
    
#     session['biometric_challenge'] = options.challenge
#     return options_to_json(options)

# @biometric_bp.route('/authenticate-verify', methods=['POST'])
# @login_required
# def verify_authentication():
#     """Step 2: Verify the fingerprint signature against the database"""
#     credential = request.get_json()
    
#     try:
#         verification = verify_authentication_response(
#             credential=credential,
#             expected_challenge=session.get('biometric_challenge'),
#             expected_origin=get_origin(),
#             expected_rp_id=get_rp_id(),
#             credential_public_key=bytes.fromhex(current_user.webauthn_public_key),
#             credential_current_sign_count=current_user.webauthn_sign_count,
#             require_user_verification=False
#         )
        
#         # Security: Prevent replay attacks by updating the sign count
#         current_user.webauthn_sign_count = verification.new_sign_count
#         db.session.commit()
        
#         return jsonify({"success": True, "message": "Terminal Unlocked!"})
        
#     except Exception as e:
#         print(f"Auth Error: {e}")
#         return jsonify({"success": False, "message": str(e)}), 400