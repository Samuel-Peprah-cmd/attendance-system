from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests

# CR80 / ID-1 standard at 300 DPI
CARD_WIDTH = 1013
CARD_HEIGHT = 638


def _safe_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_to_rgb(value, fallback=(22, 128, 144)):
    if not value:
        return fallback
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback


def _download_image(url: str, fallback_size=(300, 300), mode="RGBA"):
    if not url:
        return Image.new(mode, fallback_size, (240, 240, 240, 255))
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert(mode)
    except Exception:
        return Image.new(mode, fallback_size, (240, 240, 240, 255))


def _fit_cover(img, size):
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _fit_contain(img, size):
    target_w, target_h = size
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    resized = img.resize(new_size, Image.LANCZOS)
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    x = (target_w - new_size[0]) // 2
    y = (target_h - new_size[1]) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def _draw_text(draw, xy, text, font, fill, max_width=None, line_spacing=6):
    x, y = xy
    text = str(text or "")

    if not max_width:
        draw.text((x, y), text, font=font, fill=fill)
        return y + font.size + line_spacing

    words = text.split()
    line = ""
    lines = []

    for word in words:
        test = f"{line} {word}".strip()
        width = draw.textbbox((0, 0), test, font=font)[2]
        if width <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_spacing

    return y


def _apply_tiled_watermark(card, logo_img, body_top, body_bottom, opacity=0.016):
    if logo_img is None:
        return

    tile = _fit_contain(logo_img, (90, 90)).copy()
    alpha = tile.getchannel("A").point(lambda p: int(p * opacity * 255 / 255))
    tile.putalpha(alpha)

    start_x = 210
    end_x = CARD_WIDTH - 40
    start_y = body_top + 20
    end_y = body_bottom - 40

    step_x = 150
    step_y = 95

    row_index = 0
    for y in range(start_y, end_y, step_y):
        x_offset = 0 if row_index % 2 == 0 else 70
        for x in range(start_x + x_offset, end_x, step_x):
            card.paste(tile, (x, y), tile)
        row_index += 1


def generate_staff_id_png(staff, issued_date: str, expiry_date: str, session_text: str, public_r2_base_url: str):
    primary = _hex_to_rgb(getattr(staff.school, "primary_color", None), (22, 128, 144))
    secondary = _hex_to_rgb(getattr(staff.school, "secondary_color", None), (31, 41, 55))

    card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (247, 248, 250, 255))
    draw = ImageDraw.Draw(card)

    # Header
    header_h = 110
    draw.rectangle((0, 0, CARD_WIDTH, header_h), fill=primary)

    # Fonts
    font_school = _safe_font(34, bold=True)
    font_sub = _safe_font(20, bold=False)
    font_small = _safe_font(18, bold=True)
    font_label = _safe_font(15, bold=True)
    font_value = _safe_font(19, bold=True)
    font_name = _safe_font(38, bold=True)
    font_footer_left = _safe_font(14, bold=True)
    font_footer_right = _safe_font(11, bold=True)
    font_qr_note = _safe_font(12)

    # Header left
    logo_x = 28
    text_x = 125
    school_logo = None

    if getattr(staff.school, "logo_path", None):
        school_logo = _download_image(staff.school.logo_path, fallback_size=(70, 70))
        logo = _fit_contain(school_logo, (70, 70))
        logo_bg = Image.new("RGBA", (76, 76), (255, 255, 255, 255))
        card.paste(logo_bg, (logo_x, 18))
        card.paste(logo, (logo_x + 3, 21), logo)

    draw.text((text_x, 18), (staff.school.name or "").upper(), font=font_school, fill=(255, 255, 255))
    draw.text((text_x, 62), "STAFF ATTENDANCE CARD", font=font_sub, fill=(255, 255, 255, 225))

    # Header right
    right_label = "YEAR"
    right_value = session_text
    rl_w = draw.textbbox((0, 0), right_label, font=font_small)[2]
    rv_w = draw.textbbox((0, 0), right_value, font=font_small)[2]
    right_x = CARD_WIDTH - max(rl_w, rv_w) - 32
    draw.text((right_x, 24), right_label, font=font_small, fill=(255, 255, 255, 225))
    draw.text((CARD_WIDTH - rv_w - 32, 56), right_value, font=font_small, fill=(255, 255, 255))

    # Very transparent scattered watermark logos
    if school_logo is not None:
        _apply_tiled_watermark(card, school_logo, body_top=header_h, body_bottom=575, opacity=0.016)

    # Layout
    photo_box = (35, 150, 175, 320)
    qr_box = (808, 175, 988, 355)
    details_x = 220
    details_right_limit = 775

    # Photo
    if getattr(staff, "photo_path", None):
        photo = _download_image(staff.photo_path, fallback_size=(160, 190))
        photo = _fit_cover(photo, (photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]))
    else:
        photo = Image.new("RGBA", (photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]), (240, 240, 240, 255))

    card.paste(photo, (photo_box[0], photo_box[1]), photo)
    draw.rounded_rectangle(photo_box, radius=14, outline=(220, 220, 220), width=3)

    draw.text((40, 345), "STAFF ID", font=font_label, fill=primary)
    _draw_text(draw, (40, 372), staff.staff_code or "N/A", font_value, secondary, max_width=145, line_spacing=2)

    # Name
    draw.text((details_x, 150), "FULL NAME", font=font_label, fill=(148, 163, 184))
    _draw_text(draw, (details_x, 178), (staff.full_name or "").upper(), font_name, secondary, max_width=540, line_spacing=2)

    draw.line((details_x, 285, details_right_limit, 285), fill=(224, 227, 232), width=2)

    # Column separators
    body_top = 140
    body_bottom = 595
    draw.line((195, body_top, 195, body_bottom), fill=(225, 229, 235), width=2)
    draw.line((790, body_top, 790, body_bottom), fill=(225, 229, 235), width=2)

    # Lower content pushed down to reduce the gap above footer
    col1_x = details_x
    col2_x = 520
    row1_y = 320
    row2_y = 392
    row3_y = 464

    designation = staff.designation or "N/A"
    phone = staff.phone or "N/A"
    email = staff.email or "N/A"
    status_text = "ACTIVE" if getattr(staff, "is_active", True) else "INACTIVE"
    status_color = (22, 163, 74) if getattr(staff, "is_active", True) else (220, 38, 38)

    detail_items = [
        (col1_x, row1_y, "DESIGNATION", designation, secondary, 220),
        (col2_x, row1_y, "STATUS", status_text, status_color, 170),
        (col1_x, row2_y, "PHONE", phone, secondary, 220),
        (col2_x, row2_y, "EMAIL", email, secondary, 220),
        (col1_x, row3_y, "DATE ISSUED", issued_date, secondary, 170),
        (col2_x, row3_y, "EXPIRY", expiry_date, secondary, 220),
    ]

    for x, y, label, value, color, width in detail_items:
        draw.text((x, y), label, font=font_label, fill=primary)
        _draw_text(draw, (x, y + 22), value, font=font_value, fill=color, max_width=width, line_spacing=1)

    # IMPORTANT: this matches your current uploaded staff QR filename pattern
    qr_url = f"{public_r2_base_url.rstrip('/')}/qr_codes/staff_qr_{staff.qr_token}.png"
    qr = _download_image(qr_url, fallback_size=(180, 180))
    qr = _fit_contain(qr, (qr_box[2] - qr_box[0], qr_box[3] - qr_box[1]))

    qr_bg = Image.new("RGBA", (190, 190), (255, 255, 255, 255))
    card.paste(qr_bg, (804, 171))
    card.paste(qr, (qr_box[0], qr_box[1]), qr)

    qr_title = "SCAN FOR VERIFICATION"
    qr_note = "Keep this QR clean and visible"
    qt_w = draw.textbbox((0, 0), qr_title, font=font_label)[2]
    qn_w = draw.textbbox((0, 0), qr_note, font=font_qr_note)[2]
    qr_center_x = (qr_box[0] + qr_box[2]) // 2
    draw.text((qr_center_x - qt_w // 2, 392), qr_title, font=font_label, fill=primary)
    draw.text((qr_center_x - qn_w // 2, 417), qr_note, font=font_qr_note, fill=(107, 114, 128))

    # Footer — short and close
    footer_height = 36
    footer_y = CARD_HEIGHT - footer_height  # 602

    draw.rectangle((0, footer_y, CARD_WIDTH, CARD_HEIGHT), fill=(249, 250, 251))
    draw.line((0, footer_y, CARD_WIDTH, footer_y), fill=(229, 231, 235), width=2)

    footer_left = f"OFFICIAL {(staff.school.name or '').upper()} STAFF ATTENDANCE CARD"
    footer_right = "ATOM Gate"

    draw.text((35, footer_y + 8), footer_left, font=font_footer_left, fill=(107, 114, 128))
    fr_w = draw.textbbox((0, 0), footer_right, font=font_footer_right)[2]
    draw.text((CARD_WIDTH - fr_w - 35, footer_y + 11), footer_right, font=font_footer_right, fill=primary)

    output = BytesIO()
    card = card.convert("RGB")
    card.save(output, format="PNG", dpi=(300, 300))
    output.seek(0)
    return output


# def generate_staff_id_back_png(staff, public_r2_base_url: str):
#     primary = _hex_to_rgb(getattr(staff.school, "primary_color", None), (22, 128, 144))
#     secondary = _hex_to_rgb(getattr(staff.school, "secondary_color", None), (31, 41, 55))

#     card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (247, 248, 250, 255))
#     draw = ImageDraw.Draw(card)

#     header_h = 110
#     draw.rectangle((0, 0, CARD_WIDTH, header_h), fill=primary)

#     font_school = _safe_font(34, bold=True)
#     font_sub = _safe_font(20, bold=False)
#     font_title = _safe_font(24, bold=True)
#     font_body = _safe_font(22, bold=False)
#     font_label = _safe_font(16, bold=True)
#     font_value = _safe_font(20, bold=True)
#     font_footer_left = _safe_font(14, bold=True)
#     font_footer_right = _safe_font(11, bold=True)

#     logo_x = 28
#     text_x = 125
#     school_logo = None

#     if getattr(staff.school, "logo_path", None):
#         school_logo = _download_image(staff.school.logo_path, fallback_size=(70, 70))
#         logo = _fit_contain(school_logo, (70, 70))
#         logo_bg = Image.new("RGBA", (76, 76), (255, 255, 255, 255))
#         card.paste(logo_bg, (logo_x, 18))
#         card.paste(logo, (logo_x + 3, 21), logo)

#     draw.text((text_x, 20), (staff.school.name or "").upper(), font=font_school, fill=(255, 255, 255))
#     draw.text((text_x, 62), "STAFF IDENTIFICATION CARD — REVERSE SIDE", font=font_sub, fill=(255, 255, 255, 225))

#     if school_logo is not None:
#         wm = _fit_contain(school_logo, (250, 250)).copy()
#         alpha = wm.getchannel("A").point(lambda p: int(p * 0.04))
#         wm.putalpha(alpha)
#         card.paste(wm, ((CARD_WIDTH - 250) // 2, (CARD_HEIGHT - 250) // 2 + 10), wm)

#     title_text = "SCHOOL PROPERTY NOTICE"
#     title_w = draw.textbbox((0, 0), title_text, font=font_title)[2]
#     draw.text(((CARD_WIDTH - title_w) // 2, 145), title_text, font=font_title, fill=primary)

#     notice_text = (
#         f"This identification card is the property of {staff.school.name}. "
#         f"If found, please return it to the school or contact the school using the information below."
#     )
#     _draw_text(draw, (120, 195), notice_text, font=font_body, fill=secondary, max_width=770, line_spacing=8)

#     box1 = (90, 315, 455, 410)
#     box2 = (560, 315, 925, 410)
#     box3 = (90, 440, 925, 530)

#     for box in [box1, box2, box3]:
#         draw.rounded_rectangle(box, radius=18, outline=(220, 225, 230), width=2, fill=(250, 251, 252))

#     school_email = staff.school.profile.email_primary if staff.school.profile and staff.school.profile.email_primary else "school@email.com"
#     school_phone = staff.school.profile.phone_primary if staff.school.profile and staff.school.profile.phone_primary else "No phone available"
#     school_address = staff.school.profile.full_address if staff.school.profile and staff.school.profile.full_address else "Address not provided"

#     draw.text((115, 335), "SCHOOL EMAIL", font=font_label, fill=primary)
#     _draw_text(draw, (115, 360), school_email, font=font_value, fill=secondary, max_width=300, line_spacing=2)

#     draw.text((585, 335), "SCHOOL PHONE", font=font_label, fill=primary)
#     _draw_text(draw, (585, 360), school_phone, font=font_value, fill=secondary, max_width=300, line_spacing=2)

#     draw.text((115, 460), "SCHOOL ADDRESS", font=font_label, fill=primary)
#     _draw_text(draw, (115, 485), school_address, font=font_value, fill=secondary, max_width=760, line_spacing=2)

#     draw.rounded_rectangle((120, 548, 893, 585), radius=16, fill=(237, 247, 247))
#     warning = "Unauthorized use, duplication, transfer, or tampering of this card is prohibited."
#     ww = draw.textbbox((0, 0), warning, font=_safe_font(16, bold=True))[2]
#     draw.text(((CARD_WIDTH - ww) // 2, 558), warning, font=_safe_font(16, bold=True), fill=secondary)

#     footer_height = 36
#     footer_y = CARD_HEIGHT - footer_height

#     draw.rectangle((0, footer_y, CARD_WIDTH, CARD_HEIGHT), fill=(249, 250, 251))
#     draw.line((0, footer_y, CARD_WIDTH, footer_y), fill=(229, 231, 235), width=2)

#     footer_left = f"RETURN TO {(staff.school.name or '').upper()}"
#     footer_right = "ATOM Gate"

#     draw.text((35, footer_y + 8), footer_left, font=font_footer_left, fill=(107, 114, 128))
#     fr_w = draw.textbbox((0, 0), footer_right, font=font_footer_right)[2]
#     draw.text((CARD_WIDTH - fr_w - 35, footer_y + 11), footer_right, font=font_footer_right, fill=primary)

#     output = BytesIO()
#     card = card.convert("RGB")
#     card.save(output, format="PNG", dpi=(300, 300))
#     output.seek(0)
#     return output

def generate_staff_id_back_png(staff, public_r2_base_url: str):
    primary = _hex_to_rgb(getattr(staff.school, "primary_color", None), (22, 128, 144))
    secondary = _hex_to_rgb(getattr(staff.school, "secondary_color", None), (31, 41, 55))

    card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (247, 248, 250, 255))
    draw = ImageDraw.Draw(card)

    header_h = 110
    draw.rectangle((0, 0, CARD_WIDTH, header_h), fill=primary)

    font_school = _safe_font(34, bold=True)
    font_sub = _safe_font(20, bold=False)
    font_title = _safe_font(24, bold=True)
    font_body = _safe_font(22, bold=False)
    font_label = _safe_font(16, bold=True)
    font_value = _safe_font(20, bold=True)
    font_footer_left = _safe_font(14, bold=True)
    font_footer_right = _safe_font(11, bold=True)

    logo_x = 28
    text_x = 125
    school_logo = None

    if getattr(staff.school, "logo_path", None):
        school_logo = _download_image(staff.school.logo_path, fallback_size=(70, 70))
        logo = _fit_contain(school_logo, (70, 70))
        logo_bg = Image.new("RGBA", (76, 76), (255, 255, 255, 255))
        card.paste(logo_bg, (logo_x, 18))
        card.paste(logo, (logo_x + 3, 21), logo)

    draw.text((text_x, 18), (staff.school.name or "").upper(), font=font_school, fill=(255, 255, 255))
    draw.text((text_x, 62), "STAFF ATTENDANCE CARD", font=font_sub, fill=(255, 255, 255, 225))

    if school_logo is not None:
        wm = _fit_contain(school_logo, (250, 250)).copy()
        alpha = wm.getchannel("A").point(lambda p: int(p * 0.04))
        wm.putalpha(alpha)
        card.paste(wm, ((CARD_WIDTH - 250) // 2, (CARD_HEIGHT - 250) // 2 + 10), wm)

    title_text = "SCHOOL PROPERTY NOTICE"
    title_w = draw.textbbox((0, 0), title_text, font=font_title)[2]
    draw.text(((CARD_WIDTH - title_w) // 2, 145), title_text, font=font_title, fill=primary)

    notice_text = (
        f"This attendance card is the property of {staff.school.name}. "
        f"If found, please return it to the school or contact the school using the information below."
    )
    _draw_text(draw, (120, 195), notice_text, font=font_body, fill=secondary, max_width=770, line_spacing=8)

    box1 = (90, 305, 455, 395)
    box2 = (560, 305, 925, 395)
    box3 = (90, 410, 925, 485)

    for box in [box1, box2, box3]:
        draw.rounded_rectangle(box, radius=18, outline=(220, 225, 230), width=2, fill=(250, 251, 252))

    school_email = staff.school.contact_email or "contact@school.edu"
    school_phone = staff.school.contact_phone or "Contact Administration"
    
    school_address = staff.school.contact_address
    if not school_address or school_address.strip() == "Ghana":
        school_address = "Address pending configuration"

    school_website = getattr(staff.school.profile, 'website', None) if staff.school.profile else None
    if not school_website:
        clean_name = "".join(e for e in (staff.school.name or "school") if e.isalnum()).lower()
        school_website = f"www.{clean_name}.edu"

    draw.text((115, 325), "SCHOOL EMAIL", font=font_label, fill=primary)
    _draw_text(draw, (115, 350), school_email, font=font_value, fill=secondary, max_width=300, line_spacing=2)

    draw.text((585, 325), "SCHOOL PHONE", font=font_label, fill=primary)
    _draw_text(draw, (585, 350), school_phone, font=font_value, fill=secondary, max_width=300, line_spacing=2)

    draw.text((115, 425), "SCHOOL ADDRESS", font=font_label, fill=primary)
    _draw_text(draw, (115, 450), school_address, font=font_value, fill=secondary, max_width=760, line_spacing=2)

    web_w = draw.textbbox((0, 0), school_website, font=font_value)[2]
    draw.text(((CARD_WIDTH - web_w) // 2, 510), school_website, font=font_value, fill=primary)

    draw.rounded_rectangle((120, 545, 893, 582), radius=16, fill=(237, 247, 247))
    warning = "Unauthorized use, duplication, transfer, or tampering of this card is prohibited."
    ww = draw.textbbox((0, 0), warning, font=_safe_font(16, bold=True))[2]
    draw.text(((CARD_WIDTH - ww) // 2, 555), warning, font=_safe_font(16, bold=True), fill=secondary)

    footer_height = 36
    footer_y = CARD_HEIGHT - footer_height

    draw.rectangle((0, footer_y, CARD_WIDTH, CARD_HEIGHT), fill=(249, 250, 251))
    draw.line((0, footer_y, CARD_WIDTH, footer_y), fill=(229, 231, 235), width=2)

    footer_left = f"Authorized Signature"
    footer_right = "ATOM Gate"

    draw.text((35, footer_y + 8), footer_left, font=font_footer_left, fill=(107, 114, 128))
    fr_w = draw.textbbox((0, 0), footer_right, font=font_footer_right)[2]
    draw.text((CARD_WIDTH - fr_w - 35, footer_y + 11), footer_right, font=font_footer_right, fill=primary)

    output = BytesIO()
    card = card.convert("RGB")
    card.save(output, format="PNG", dpi=(300, 300))
    output.seek(0)
    return output