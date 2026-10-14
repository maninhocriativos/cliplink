import unittest
import os
import time
import json
from unittest.mock import patch

from desktop_app import (
    ClipLinkApp,
    _base_options,
    _check_content_scope,
    _append_lab_evidence,
    _duration_label,
    _confine_output_path,
    _format_selector,
    _load_history,
    _safe_metadata,
    _save_history,
    _write_lab_report,
    _read_update_manifest,
    _version_tuple,
)
from pathlib import Path
from tempfile import TemporaryDirectory


class DesktopLogicTests(unittest.TestCase):
    def test_format_selector_respects_selected_height(self):
        self.assertEqual(_format_selector("720p"), "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b")
        self.assertEqual(_format_selector("Melhor disponível"), "bv*+ba/b")

    def test_metadata_is_reduced_to_display_fields(self):
        result = _safe_metadata({
            "title": "Vídeo de teste",
            "extractor_key": "TestSiteIE",
            "duration": 83.7,
            "formats": [{"height": 720}, {"height": "1080"}, {"height": None}],
            "description": "Este campo não deve ser exibido",
        })
        self.assertEqual(result["title"], "Vídeo de teste")
        self.assertEqual(result["platform"], "Testsite")
        self.assertEqual(result["duration"], 83)
        self.assertEqual(result["max_height"], 1080)
        self.assertEqual(result["available_heights"], [1080, 720])
        self.assertNotIn("description", result)

    def test_negative_duration_is_treated_as_unavailable(self):
        result = _safe_metadata({"duration": -1})
        self.assertIsNone(result["duration"])

    def test_instagram_single_resolution_falls_back_to_available_format(self):
        selector = _format_selector("1080p")
        self.assertTrue(selector.endswith("/bv*+ba/b"))

    def test_image_selector_uses_original_media(self):
        self.assertEqual(_format_selector("Melhor disponÃ­vel", "Imagem"), "best")

    def test_image_metadata_is_identified_without_duration(self):
        result = _safe_metadata({
            "title": "Imagem de teste",
            "extractor_key": "Generic",
            "ext": "jpg",
            "mime_type": "image/jpeg",
        })
        self.assertEqual(result["media_kind"], "image")
        self.assertEqual(result["extension"], "jpg")
        self.assertIsNone(result["duration"])

    def test_story_url_is_identified_from_public_url(self):
        result = _safe_metadata({
            "title": "Story de teste",
            "extractor_key": "Instagram",
            "ext": "mp4",
        }, "https://www.instagram.com/stories/example/123/")
        self.assertEqual(result["media_kind"], "story")

    def test_public_live_content_is_not_blocked_by_cliplink(self):
        _check_content_scope({"is_live": True, "availability": "public"}, "https://example.com/live")

    def test_private_availability_is_left_to_the_site_and_user_authorization(self):
        _check_content_scope({"availability": "private"}, "https://example.com/private")

    def test_download_has_no_artificial_size_cap_and_retries_transient_errors(self):
        options = _base_options()
        self.assertNotIn("max_filesize", options)
        self.assertEqual(options["retries"], 3)
        self.assertEqual(options["fragment_retries"], 3)

    def test_tiktok_uses_yt_dlp_mobile_fallback_without_credentials(self):
        options = _base_options()
        app_info = options["extractor_args"]["tiktok"]["app_info"]
        self.assertEqual(len(app_info), 1)
        self.assertRegex(app_info[0], r"^7\d{18}$")

    def test_update_manifest_resolves_installer_and_versions(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size):
                return json.dumps({
                    "version": "0.4.7",
                    "installer_url": "ClipLink-Setup.exe",
                }).encode()

        with patch.dict(os.environ, {"CLIPLINK_UPDATE_URL": "https://updates.example/releases/update.json"}), \
                patch("desktop_app.urllib.request.urlopen", return_value=Response()):
            manifest = _read_update_manifest()
        self.assertEqual(manifest["installer_url"], "https://updates.example/releases/ClipLink-Setup.exe")
        self.assertGreater(_version_tuple(manifest["version"]), _version_tuple("0.4.6"))

    def test_lab_report_is_local_and_does_not_record_credentials(self):
        with TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"LOCALAPPDATA": temp}):
                report_path = _write_lab_report(
                    "https://example.com/video/123",
                    {"formats": [{"format_id": "18", "ext": "mp4", "height": 720, "vcodec": "h264", "acodec": "aac"}]},
                    {
                        "title": "Teste",
                        "platform": "Example",
                        "media_kind": "video",
                        "content_type": "video",
                        "availability": "public",
                        "is_live": False,
                        "has_drm": False,
                        "format_count": 1,
                        "estimated_size": 1024,
                        "has_audio": True,
                        "has_video": True,
                        "available_heights": [720],
                    },
                )
                self.assertIsNotNone(report_path)
                payload = report_path.read_text(encoding="utf-8")
                self.assertIn('"credentials_used": false', payload)
                self.assertIn('"format_id": "18"', payload)

    def test_lab_report_records_evidence_hash(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "report.json"
            report.write_text('{"evidence": []}', encoding="utf-8")
            media = root / "evidence.jpg"
            media.write_bytes(b"authorized-evidence")
            self.assertTrue(_append_lab_evidence(report, media))
            payload = report.read_text(encoding="utf-8")
            self.assertIn("evidence.jpg", payload)
            self.assertIn("sha256", payload)

    def test_history_round_trips_local_files_and_ignores_missing_entries(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            video = root / "video.mp4"
            video.write_bytes(b"video")
            history_file = root / "state" / "history.json"
            entries = [{"title": "Vídeo", "platform": "Instagram", "path": str(video), "saved_at": "13/10/2026 14:00"}]
            self.assertTrue(_save_history(history_file, entries))
            self.assertEqual(_load_history(history_file), entries)
            self.assertTrue(_save_history(history_file, [*entries, {"title": "Removido", "path": str(root / "gone.mp4")}]))
            self.assertEqual(_load_history(history_file), entries)

    def test_duration_label_handles_missing_and_hour_values(self):
        self.assertEqual(_duration_label(None), "Duração indisponível")
        self.assertEqual(_duration_label(3723), "1:02:03")
        self.assertEqual(_duration_label(61), "1:01 min")

    def test_tiktok_extractor_error_is_explained_without_raw_trace(self):
        message = ClipLinkApp._friendly_error(
            Exception("[TikTok] Unexpected response from webpage request")
        )
        self.assertIn("Plataformas podem mudar", message)
        self.assertNotIn("Traceback", message)

    def test_unavailable_instagram_resolution_has_actionable_message(self):
        message = ClipLinkApp._friendly_error(
            Exception("ERROR: [Instagram] Requested format is not available. Use --list-formats")
        )
        self.assertIn("Melhor disponível", message)
        self.assertNotIn("--list-formats", message)

    def test_partial_files_created_after_start_are_cleaned(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            old_part = root / "old.part"
            old_part.write_bytes(b"keep")
            started_at = time.time()
            os.utime(old_part, (started_at - 10, started_at - 10))
            new_part = root / "new.part"
            new_part.write_bytes(b"remove")
            new_part.touch()
            ytdl = root / "new.ytdl"
            ytdl.write_bytes(b"remove")
            ytdl.touch()

            ClipLinkApp._cleanup_partial_files(root, started_at - 1)

            self.assertTrue(old_part.exists())
            self.assertFalse(new_part.exists())
            self.assertFalse(ytdl.exists())

    def test_output_path_cannot_escape_selected_folder(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "downloads"
            root.mkdir()
            safe = root / "video.mp4"
            self.assertEqual(_confine_output_path(safe, root), safe.resolve())
            with self.assertRaises(ValueError):
                _confine_output_path(root.parent / "outside.mp4", root)


if __name__ == "__main__":
    unittest.main()
