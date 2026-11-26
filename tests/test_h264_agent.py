import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lunexpc_h264_agent", ROOT/"agent/windows/h264_agent.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class H264AgentTests(unittest.TestCase):
    def test_video_key_is_derived_not_reusable_as_mcp_secret(self):
        upstream = "secure-device-agent-secret-for-test-only-123"
        video = module.derived_video_key(upstream)
        self.assertEqual(len(video),64)
        self.assertNotEqual(video,upstream)
        self.assertNotEqual(video,module.derived_video_key(upstream+"different"))
    def test_codec_profiles_bounded_and_shell_free(self):
        for name,(width,height,fps,bitrate) in module.PROFILES.items():
            cmd=module.ffmpeg_command("C:/ffmpeg.exe",name)
            self.assertEqual(cmd[0],"C:/ffmpeg.exe")
            self.assertIn("gdigrab",cmd)
            self.assertIn("h264_nvenc",cmd)
            self.assertIn("pipe:1",cmd)
            self.assertIn("baseline",cmd)
            self.assertIn(str(fps),cmd)
            self.assertLessEqual(fps,30)
        with self.assertRaises(ValueError):module.ffmpeg_command("x","other")
    def test_no_file_recording_or_unrestricted_bind(self):
        source=(ROOT/"agent/windows/h264_agent.py").read_text()
        self.assertIn('("127.0.0.1", PORT)',source)
        self.assertIn("hmac.compare_digest",source)
        self.assertIn("stream_lock.acquire(blocking=False)",source)
        self.assertIn("MAX_SECONDS = 180",source)
        self.assertIn("MAX_BYTES = 100 * 1024 * 1024",source)
        self.assertIn("process.terminate()",source)
        self.assertNotIn("shell=True",source)
        self.assertNotIn("0.0.0.0",source)
