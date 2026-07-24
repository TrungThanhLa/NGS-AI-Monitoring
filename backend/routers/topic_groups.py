from fastapi import APIRouter, Depends

from backend.ai.prompts.v1 import TOPIC_GROUPS
from backend.auth.dependencies import require_permission
from backend.models import User

router = APIRouter(prefix="/api/topic-groups", tags=["topic-groups"])


@router.get("")
def list_topic_groups(_user: User = Depends(require_permission("campaign", "view"))):
    # Chỉ đọc — 8 nhóm chủ đề là hằng số gắn với prompt AI (backend/ai/prompts/v1.py),
    # không phải danh mục CRUD được: sửa/xóa qua UI sẽ không đồng bộ với prompt đang chạy
    # (rủi ro drift + prompt injection nếu cho nhập free text feed thẳng vào AI — xem
    # thảo luận quyết định không xây CRUD cho nhóm này). Endpoint này chỉ để FE hiển thị
    # đúng danh sách đang thực sự dùng, tránh trùng lặp hardcode ở FE lệch khỏi backend.
    return {"topic_groups": TOPIC_GROUPS}
