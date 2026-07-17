import os

from fastapi import HTTPException, UploadFile

from backend.models import User

_ALLOWED_AVATAR_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB


def avatar_dir() -> str:
    base = os.environ.get("STORAGE_PATH", "./storage")
    path = os.path.join(base, "avatars")
    os.makedirs(path, exist_ok=True)
    return path


def save_uploaded_avatar(user: User, file: UploadFile) -> None:
    """Validate + lưu file avatar cho user, cập nhật user.avatar_path — không tự commit,
    dùng chung transaction với route gọi nó (giống log_action)."""
    ext = _ALLOWED_AVATAR_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(status_code=422, detail="Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP")

    content = file.file.read()
    if len(content) > _MAX_AVATAR_SIZE:
        raise HTTPException(status_code=422, detail="Ảnh không được vượt quá 2MB")

    # Xóa file avatar cũ nếu tồn tại (có thể khác đuôi file với ảnh mới) — tránh rác file mồ côi
    if user.avatar_path:
        old_path = os.path.join(avatar_dir(), user.avatar_path)
        if os.path.exists(old_path):
            os.remove(old_path)

    filename = f"{user.user_id}.{ext}"
    with open(os.path.join(avatar_dir(), filename), "wb") as out:
        out.write(content)
    user.avatar_path = filename


def avatar_file_path(user: User) -> str | None:
    if not user.avatar_path:
        return None
    path = os.path.join(avatar_dir(), user.avatar_path)
    return path if os.path.exists(path) else None
