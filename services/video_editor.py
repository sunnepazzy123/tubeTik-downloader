import os
import subprocess
import tempfile
import uuid


def run_ffmpeg(command: list[str]):
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"FFmpeg failed:\n{exc.stderr}"
        ) from exc

def add_logo(
    input_path: str,
    logo_path: str,
    output_path: str,
    width: int = 140,
    margin: int = 24,
):
    command = [
        "ffmpeg",
        "-y",

        "-i",
        input_path,

        "-i",
        logo_path,

        "-filter_complex",
        (
            f"[1:v]scale={width}:-1[logo];"
            f"[0:v][logo]overlay="
            f"W-w-{margin}:H-h-{margin}"
        ),

        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "18",

        "-c:a",
        "copy",

        "-movflags",
        "+faststart",

        output_path,
    ]

    run_ffmpeg(command)

    return output_path


def trim_video(
    input_path: str,
    output_path: str,
    start_seconds: float,
    end_seconds: float,
):
    if end_seconds <= start_seconds:
        raise ValueError("end_seconds must be greater than start_seconds")

    duration = end_seconds - start_seconds

    command = [
        "ffmpeg",
        "-y",
        "-ss", str(start_seconds),
        "-i", input_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    run_ffmpeg(command)

    return output_path


def remove_intro_outro(
    input_path: str,
    output_path: str,
    intro_seconds: float = 0,
    outro_seconds: float = 0,
):
    duration = get_video_duration(input_path)

    start = max(0, intro_seconds)
    end = duration - max(0, outro_seconds)

    if end <= start:
        raise ValueError(
            "Intro/outro values remove the entire video"
        )

    return trim_video(
        input_path=input_path,
        output_path=output_path,
        start_seconds=start,
        end_seconds=end,
    )


def cut_segments(
    input_path: str,
    segments: list[tuple[float, float]],
    output_dir: str,
) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)

    generated_files = []

    for index, (start, end) in enumerate(segments):
        output_path = os.path.join(
            output_dir,
            f"segment_{index}_{uuid.uuid4().hex}.mp4",
        )

        trim_video(
            input_path=input_path,
            output_path=output_path,
            start_seconds=start,
            end_seconds=end,
        )

        generated_files.append(output_path)

    return generated_files


def join_videos(
    video_paths: list[str],
    output_path: str,
):
    if not video_paths:
        raise ValueError("No videos supplied")

    concat_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
    )

    try:
        for path in video_paths:
            absolute_path = os.path.abspath(path)

            safe_path = absolute_path.replace(
                "'",
                "'\\''",
            )

            concat_file.write(
                f"file '{safe_path}'\n"
            )

        concat_file.close()

        command = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file.name,

            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",

            "-c:a", "aac",
            "-b:a", "192k",

            "-movflags", "+faststart",

            output_path,
        ]

        run_ffmpeg(command)

        return output_path

    finally:
        if os.path.exists(concat_file.name):
            os.remove(concat_file.name)


def zoom_video(
    input_path: str,
    output_path: str,
    zoom: float = 1.08,
):
    if zoom <= 1:
        raise ValueError("zoom must be greater than 1")

    crop_width = 1 / zoom
    crop_height = 1 / zoom

    video_filter = (
        f"crop=iw*{crop_width}:ih*{crop_height}:"
        f"(iw-iw*{crop_width})/2:"
        f"(ih-ih*{crop_height})/2,"
        "scale=iw:ih"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,

        "-vf", video_filter,

        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",

        "-c:a", "copy",

        "-movflags", "+faststart",

        output_path,
    ]

    run_ffmpeg(command)

    return output_path


def blur_region(
    input_path: str,
    output_path: str,
    x: int,
    y: int,
    width: int,
    height: int,
    blur_strength: int = 20,
):
    filter_complex = (
        f"[0:v]split=2[base][crop];"
        f"[crop]crop={width}:{height}:{x}:{y},"
        f"boxblur={blur_strength}:{blur_strength}[blur];"
        f"[base][blur]overlay={x}:{y}[v]"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,

        "-filter_complex",
        filter_complex,

        "-map", "[v]",
        "-map", "0:a?",

        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",

        "-c:a", "aac",
        "-b:a", "192k",

        "-movflags", "+faststart",

        output_path,
    ]

    run_ffmpeg(command)

    return output_path



def reframe_video(
    input_path: str,
    output_path: str,
    aspect_ratio: str,
    quality: str = "balanced",
):
    import subprocess

    dimensions = {
        "4:5": (1080, 1350),
        "1:1": (1080, 1080),
        "16:9": (1920, 1080),
    }

    if aspect_ratio not in dimensions:
        raise ValueError(
            f"Unsupported aspect ratio: {aspect_ratio}"
        )

    width, height = dimensions[
        aspect_ratio
    ]

    quality_settings = {
        "fast": ("veryfast", 23),
        "balanced": ("medium", 20),
        "high": ("slow", 18),
    }

    preset, crf = quality_settings.get(
        quality,
        quality_settings["balanced"],
    )

    video_filter = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )

    command = [
        "ffmpeg",
        "-y",

        "-i",
        input_path,

        "-vf",
        video_filter,

        "-c:v",
        "libx264",

        "-preset",
        preset,

        "-crf",
        str(crf),

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-movflags",
        "+faststart",

        output_path,
    ]

    subprocess.run(
        command,
        check=True,
    )

    

def reframe_vertical(
    input_path: str,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
):
    video_filter = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,

        "-vf", video_filter,

        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",

        "-c:a", "aac",
        "-b:a", "192k",

        "-movflags", "+faststart",

        output_path,
    ]

    run_ffmpeg(command)

    return output_path


def get_video_duration(
    input_path: str,
) -> float:
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        input_path,
    ]

    result = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return float(result.stdout.strip())


def safe_delete(path: str):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as exc:
            print(
                f"Could not delete {path}: {exc}"
            )