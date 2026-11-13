"""The promo videos of the landing page: public (no token), served in ranges, and nothing else under their prefix is public.

No database is needed: the app is not started (no lifespan), and the public paths never reach the database."""

import os

from fastapi.testclient import TestClient

from main import AD_DIR, app


def test_the_promo_videos_are_public_and_served_in_ranges():
    res = TestClient(app).get("/api/v1/media/omnixon-ad-ru.mp4", headers={"Range": "bytes=0-1023"})

    assert res.status_code == 206
    assert res.headers["content-type"] == "video/mp4"
    assert len(res.content) == 1024


def test_both_cuts_are_in_the_folder_the_app_serves():
    for lang in ("ru", "en"):
        assert os.path.isfile(os.path.join(AD_DIR, f"omnixon-ad-{lang}.mp4"))
        assert TestClient(app).head(f"/api/v1/media/omnixon-ad-{lang}.mp4").status_code == 200


def test_a_missing_video_is_not_found_and_not_refused_for_its_token():
    assert TestClient(app).get("/api/v1/media/no-such-video.mp4").status_code == 404


def test_the_rest_of_the_api_still_needs_a_token():
    assert TestClient(app).get("/api/v1/agents/self").status_code == 403
