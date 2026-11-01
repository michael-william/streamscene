"""The update-check response must carry what the client needs to install."""
from uuid import uuid4

from streamscene.api.schemas import UpdateCheckResponse


def test_check_response_keeps_update_id_and_hash():
    uid = uuid4()
    info = {
        "update_available": True, "version": "1.4.0", "update_id": uid,
        "is_mandatory": False, "package_size": 10, "package_hash": "ab" * 32,
        "changelog": "", "current_version": "1.3.0",
    }
    out = UpdateCheckResponse(**info).model_dump(mode="json")
    assert out["update_id"] == str(uid)
    assert out["package_hash"] == "ab" * 32


def test_check_response_no_update():
    out = UpdateCheckResponse(update_available=False, current_version="1.4.0").model_dump()
    assert out["update_id"] is None and out["package_hash"] is None
