"""
EDITOR — FFmpeg assembly agent.
Downloads video (if cloud), generates captions, burns them in,
adds disclaimer card, produces 16:9 master and 9:16 short clip.
"""

import os
import subprocess
import logging
import requests
from core.registry import VideoRegistry

log = logging.getLogger('forge.editor')

MEDIA_DIR = os.getenv('FORGE_MEDIA_DIR', '/opt/forge/media')
ASSETS_DIR = os.getenv('FORGE_SOULS_DIR', '/opt/forge/souls') + '/assets'
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
WHISPER_PROVIDER = os.getenv('WHISPER_PROVIDER', 'local')

# Dimensions per format
_FORMAT_DIMS = {
    'youtube_long': (1920, 1080),
    'linkedin': (1920, 1080),
    'youtube_short': (1080, 1920),
    'tiktok': (1080, 1920),
    'reels': (1080, 1920),
}

DISCLAIMER_LINES = [
    "DISCLAIMER",
    "This content is for educational and informational purposes only.",
    "It does not constitute legal advice and should not be relied upon as such.",
    "Consult a licensed attorney for advice specific to your situation.",
]


class Editor:
    def assemble(self, video_id: str, soul_name: str, video_path: str, audio_path: str,
                 script: str, format: str = 'youtube_long', video_url: str = None) -> dict:
        reg = VideoRegistry()
        reg.update(video_id, status='editing')

        job_dir = os.path.join(MEDIA_DIR, video_id)
        os.makedirs(job_dir, exist_ok=True)

        # Download cloud video if no local path yet
        if not video_path and video_url:
            video_path = self._download(video_url, os.path.join(job_dir, 'avatar_raw.mp4'))

        # Generate captions (None when Whisper unavailable — skip overlay)
        srt_path = self._captions(audio_path=audio_path, job_dir=job_dir, script=script)

        # Assemble final — burn captions only when we have properly timed SRT
        assembled_path = os.path.join(job_dir, 'assembled.mp4')
        if srt_path:
            self._burn_captions(video_path=video_path, srt_path=srt_path, out_path=assembled_path)
        else:
            self._copy_video(video_path=video_path, out_path=assembled_path)

        # Append legal disclaimer end card
        w, h = _FORMAT_DIMS.get(format, (1920, 1080))
        card_path = self._disclaimer_card(job_dir=job_dir, width=w, height=h)
        final_path = os.path.join(job_dir, 'final.mp4')
        self._concat_videos([assembled_path, card_path], final_path)

        # Generate thumbnail
        thumb_path = self._thumbnail(video_path=assembled_path, job_dir=job_dir)

        # Short clip for Shorts/TikTok (first 60 seconds if long-form)
        short_path = None
        if format in ('youtube_long',):
            short_path = self._make_short(final_path, job_dir)

        reg.update(video_id, video_path=final_path, thumbnail_path=thumb_path, status='edited')
        log.info(f"[editor] {video_id} → final: {final_path}")

        return {
            'video_id': video_id,
            'final_path': final_path,
            'short_path': short_path,
            'thumbnail_path': thumb_path,
            'srt_path': srt_path,
        }

    def _download(self, url: str, out_path: str) -> str:
        r = requests.get(url, stream=True, timeout=120)
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return out_path

    def _captions(self, audio_path: str, job_dir: str, script: str):
        if WHISPER_PROVIDER != 'local':
            return None  # No timed transcript; skip subtitle overlay to keep avatar visible
        import whisper  # optional dep — install openai-whisper separately if needed
        srt_path = os.path.join(job_dir, 'captions.srt')
        model = whisper.load_model(WHISPER_MODEL)
        result = model.transcribe(audio_path, word_timestamps=True)
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(self._to_srt(result['segments']))
        return srt_path

    def _burn_captions(self, video_path: str, srt_path: str, out_path: str):
        srt_escaped = srt_path.replace('\\', '/').replace(':', '\\:')
        filter_str = (
            f"subtitles='{srt_escaped}':"
            "force_style='FontName=Arial,FontSize=14,Bold=1,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'"
        )
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-vf', filter_str,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            out_path
        ]
        self._run(cmd)

    def _thumbnail(self, video_path: str, job_dir: str) -> str:
        thumb_path = os.path.join(job_dir, 'thumbnail.jpg')
        cmd = ['ffmpeg', '-y', '-i', video_path, '-ss', '00:00:03', '-vframes', '1',
               '-vf', 'scale=1280:720', thumb_path]
        self._run(cmd)
        return thumb_path

    def _make_short(self, video_path: str, job_dir: str) -> str:
        short_path = os.path.join(job_dir, 'short.mp4')
        # Crop to 9:16 center and trim to 59 seconds
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-t', '59',
            '-vf', 'crop=ih*9/16:ih,scale=1080:1920',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            short_path
        ]
        self._run(cmd)
        return short_path

    def _disclaimer_card(self, job_dir: str, width: int, height: int) -> str:
        card_path = os.path.join(job_dir, 'disclaimer_card.mp4')
        # Build stacked drawtext filters — one per line, centered vertically
        line_spacing = 60
        total_h = len(DISCLAIMER_LINES) * line_spacing
        drawtext_parts = []
        for i, line in enumerate(DISCLAIMER_LINES):
            escaped = line.replace('\\', '\\\\').replace("'", "\\'").replace(':', '\\:')
            size = 44 if i == 0 else 30
            y = f"(h-{total_h})/2+{i * line_spacing}"
            drawtext_parts.append(
                f"drawtext=text='{escaped}':fontcolor=white:fontsize={size}"
                f":x=(w-text_w)/2:y={y}"
            )
        vf = ','.join(drawtext_parts)
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', f'color=black:size={width}x{height}:rate=30',
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-t', '5',
            card_path,
        ]
        self._run(cmd)
        return card_path

    def _concat_videos(self, video_paths: list, out_path: str):
        list_path = out_path + '.txt'
        with open(list_path, 'w') as f:
            for p in video_paths:
                f.write(f"file '{p}'\n")
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0', '-i', list_path,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            out_path,
        ]
        self._run(cmd)
        os.remove(list_path)

    def _copy_video(self, video_path: str, out_path: str):
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            out_path
        ]
        self._run(cmd)

    def _run(self, cmd: list):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")

    def _to_srt(self, segments: list) -> str:
        lines = []
        for i, seg in enumerate(segments, 1):
            start = self._fmt_ts(seg['start'])
            end = self._fmt_ts(seg['end'])
            lines.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n")
        return '\n'.join(lines)

    def _fmt_ts(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
