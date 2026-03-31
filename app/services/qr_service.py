import qrcode
import io
from app.services.storage_helper import upload_file_to_r2

def generate_student_qr(qr_token):
    # This encodes the unique safety token into a QR image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_token)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # 1. Define the filename (adding a folder prefix keeps your bucket organized)
    filename = f"qr_codes/qr_{qr_token}.png"
    
    # 2. Save the image to an in-memory buffer instead of the hard drive
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    raw_bytes = img_bytes.getvalue()
    
    # 3. Upload directly to Cloudflare R2
    public_url = upload_file_to_r2(raw_bytes, filename, content_type="image/png")
    
    # 4. Return the new Cloudflare URL (instead of the local filename) 
    # so your database can save the live link!
    if public_url:
        return public_url
    else:
        # Fallback just in case the upload fails
        return None








# import qrcode
# import os
# from flask import current_app

# def generate_student_qr(qr_token):
#     # This encodes the unique safety token into a QR image
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=10,
#         border=4,
#     )
#     qr.add_data(qr_token)
#     qr.make(fit=True)

#     img = qr.make_image(fill_color="black", back_color="white")
    
#     # Define filename and path
#     filename = f"qr_{qr_token}.png"
#     filepath = os.path.join(current_app.root_path, 'static/qr_codes', filename)
    
#     # Save the file
#     img.save(filepath)
#     return filename