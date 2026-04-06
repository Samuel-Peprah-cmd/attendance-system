from app.models.complaints import ComplaintParticipant


def is_thread_participant(user, thread):
    if not user or not getattr(user, "id", None):
        return False

    return ComplaintParticipant.query.filter_by(
        thread_id=thread.id,
        user_id=user.id
    ).first() is not None


def can_access_thread(user, thread):
    if not user or not getattr(user, "id", None):
        return False

    if not is_thread_participant(user, thread):
        return False

    if user.role == "super_admin":
        return thread.thread_type == "school_support"

    if user.role == "school_admin":
        return user.school_id == thread.school_id

    if user.role == "parent":
        return thread.thread_type == "parent_school"

    return False