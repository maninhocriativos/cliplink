import unittest
from unittest.mock import patch

import url_safety
from url_safety import validate_url


class URLValidationTests(unittest.TestCase):
    def test_rejects_non_http_schemes(self):
        with self.assertRaises(ValueError):
            validate_url("file:///etc/passwd")

    def test_rejects_localhost(self):
        with self.assertRaises(ValueError):
            validate_url("http://localhost/video.mp4")

    def test_rejects_loopback_ip(self):
        with self.assertRaises(ValueError):
            validate_url("http://127.0.0.1/video.mp4")

    def test_rejects_private_dns_resolution(self):
        fake_answer = (None, None, None, None, ("10.0.0.12", 0))
        with patch.object(url_safety.socket, "getaddrinfo", return_value=[fake_answer]):
            with self.assertRaises(ValueError):
                validate_url("https://media.example/video.mp4")

    def test_accepts_public_dns_resolution(self):
        fake_answer = (None, None, None, None, ("93.184.216.34", 0))
        with patch.object(url_safety.socket, "getaddrinfo", return_value=[fake_answer]):
            self.assertEqual(validate_url("https://media.example/video.mp4"), "https://media.example/video.mp4")

    def test_rejects_unusual_ports(self):
        with self.assertRaises(ValueError):
            validate_url("https://example.com:8443/video")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(ValueError):
            validate_url("https://user:password@example.com/video")

    def test_rejects_control_characters(self):
        with self.assertRaises(ValueError):
            validate_url("https://example.com/video\nnext")


if __name__ == "__main__":
    unittest.main()
