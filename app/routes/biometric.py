# app/routes/biometric.py
import json
from flask import Blueprint, request, session, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from webauthn.helpers.structs import PublicKeyCredentialDescriptor
from webauthn import generate_registration_options, verify_registration_response, options_to_json
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, PublicKeyCredentialType, AuthenticatorSelectionCriteria, UserVerificationRequirement
from webauthn import generate_authentication_options, verify_authentication_response

biometric_bp = Blueprint('biometric', __name__)

def get_rp_id():
    # WebAuthn strictly requires the domain name without ports or schemes
    return request.host.split(':')[0]

def get_origin():
    # WebAuthn strictly requires the exact scheme and hostname
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    return f"{scheme}://{request.host}"

@biometric_bp.route('/register-options', methods=['POST'])
@login_required
def get_register_options():
    """Step 1: Server creates a cryptographic challenge for the tablet/laptop"""
    options = generate_registration_options(
        rp_id=get_rp_id(),
        rp_name="ATOM Gate Security",
        user_id=str(current_user.id).encode(), # Must be encoded to bytes
        user_name=current_user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        )
    )
    
    # Save the challenge in the session so we can verify it in Step 2
    session['biometric_challenge'] = options.challenge
    
    # Convert the Python object into perfect JSON for the browser
    return options_to_json(options)

@biometric_bp.route('/register-verify', methods=['POST'])
@login_required
def verify_registration():
    """Step 2: Browser sends the fingerprint signature back to be verified"""
    credential = request.get_json()
    
    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=session.get('biometric_challenge'),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            require_user_verification=False
        )
        
        # 🟢 SUCCESS! Save the public keys to the database
        current_user.webauthn_id = verification.credential_id.hex()
        current_user.webauthn_public_key = verification.credential_public_key.hex()
        current_user.webauthn_sign_count = verification.sign_count
        db.session.commit()
        
        return jsonify({"success": True, "message": "Biometric device registered successfully!"})
        
    except Exception as e:
        print(f"Biometric Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 400

# @biometric_bp.route('/authenticate-options', methods=['POST'])
# @login_required
# def get_auth_options():
#     """Step 1: Ask the device to prove it has the matching fingerprint"""
#     if not current_user.webauthn_id:
#         return jsonify({"success": False, "message": "No biometrics registered."}), 400
        
#     options = generate_authentication_options(
#         rp_id=get_rp_id(),
#         allow_credentials=[{
#             "type": "public-key",
#             "id": bytes.fromhex(current_user.webauthn_id)
#         }],
#         user_verification=UserVerificationRequirement.PREFERRED
#     )
    
#     session['biometric_challenge'] = options.challenge
#     return options_to_json(options)

@biometric_bp.route('/authenticate-options', methods=['POST'])
@login_required
def get_auth_options():
    """Step 1: Ask the device to prove it has the matching fingerprint"""
    if not current_user.webauthn_id:
        return jsonify({"success": False, "message": "No biometrics registered."}), 400
        
    options = generate_authentication_options(
        rp_id=get_rp_id(),
        allow_credentials=[PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY, # 🚨 FIX: Using the official Enum instead of a string!
            id=bytes.fromhex(current_user.webauthn_id)
        )],
        user_verification=UserVerificationRequirement.PREFERRED
    )
    
    session['biometric_challenge'] = options.challenge
    return options_to_json(options)

@biometric_bp.route('/authenticate-verify', methods=['POST'])
@login_required
def verify_authentication():
    """Step 2: Verify the fingerprint signature against the database"""
    credential = request.get_json()
    
    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=session.get('biometric_challenge'),
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            credential_public_key=bytes.fromhex(current_user.webauthn_public_key),
            credential_current_sign_count=current_user.webauthn_sign_count,
            require_user_verification=False
        )
        
        # Security: Prevent replay attacks by updating the sign count
        current_user.webauthn_sign_count = verification.new_sign_count
        db.session.commit()
        
        return jsonify({"success": True, "message": "Terminal Unlocked!"})
        
    except Exception as e:
        print(f"Auth Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 400