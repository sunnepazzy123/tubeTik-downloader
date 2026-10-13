import os
import subprocess
import uuid

from services.overlay_detector import detect_overlays
from services.overlay_tracker import track_overlays
from services.mask_builder import build_mask_video


def clean_video_overlays_auto(
    input_path: str,
    output_dir: str | None = None,
) -> str:
    """
    Automatically clean overlays from a video.

    Flow:
        1. Detect overlays
        2. Track them through the video
        3. Build a frame-by-frame mask
        4. Send video + mask to AI inpainting
        5. Restore original audio
        6. Return final cleaned video
    """

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Input video does not exist: {input_path}"
        )

    if output_dir is None:
        output_dir = os.path.dirname(input_path)

    os.makedirs(output_dir, exist_ok=True)

    job_id = uuid.uuid4().hex

    mask_path = os.path.join(
        output_dir,
        f"mask_{job_id}.mp4",
    )

    inpainted_path = os.path.join(
        output_dir,
        f"inpainted_{job_id}.mp4",
    )

    final_path = os.path.join(
        output_dir,
        f"cleaned_{job_id}.mp4",
    )

    try:
        # ---------------------------------
        # 1. Detect possible overlays
        # ---------------------------------

        detections = detect_overlays(
            input_path
        )

        if not detections:
            print("No overlays detected.")

            return input_path

        print(
            f"Detected {len(detections)} overlay(s)"
        )

        # ---------------------------------
        # 2. Track overlays frame-by-frame
        # ---------------------------------

        tracks = track_overlays(
            input_path,
            detections,
        )

        if not tracks:
            print("No overlay tracks created.")

            return input_path

        # ---------------------------------
        # 3. Build mask video
        # ---------------------------------

        build_mask_video(
            input_path=input_path,
            tracks=tracks,
            output_path=mask_path,
        )

        if not os.path.exists(mask_path):
            raise RuntimeError(
                "Mask video was not created."
            )

        # ---------------------------------
        # 4. AI video inpainting
        # ---------------------------------

        run_video_inpainting(
            input_path=input_path,
            mask_path=mask_path,
            output_path=inpainted_path,
        )

        if not os.path.exists(inpainted_path):
            raise RuntimeError(
                "AI inpainting did not produce "
                "an output video."
            )

        # ---------------------------------
        # 5. Restore original audio
        # ---------------------------------

        merge_original_audio(
            original_video=input_path,
            cleaned_video=inpainted_path,
            output_path=final_path,
        )

        if not os.path.exists(final_path):
            raise RuntimeError(
                "Final cleaned video "
                "was not created."
            )

        return final_path

    finally:
        # Intermediate files can be removed
        safe_delete(mask_path)
        safe_delete(inpainted_path)


def run_video_inpainting(
    input_path: str,
    mask_path: str,
    output_path: str,
):
    """
    Call your AI video-inpainting worker.

    VideoPainter/another video-inpainting
    model should receive:

        input video
        +
        mask video

    and generate output_path.
    """

    command = [
        "python",
        "workers/video_inpainting.py",

        "--input",
        input_path,

        "--mask",
        mask_path,

        "--output",
        output_path,
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.stdout:
            print(result.stdout)

    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Video inpainting failed:\n"
            f"{exc.stderr}"
        ) from exc


def merge_original_audio(
    original_video: str,
    cleaned_video: str,
    output_path: str,
):
    """
    Take video from AI-cleaned output
    and audio from original video.
    """

    command = [
        "ffmpeg",
        "-y",

        # AI-cleaned video
        "-i",
        cleaned_video,

        # Original video containing audio
        "-i",
        original_video,

        # Video from first input
        "-map",
        "0:v:0",

        # Audio from original video
        "-map",
        "1:a:0?",

        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "18",

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-movflags",
        "+faststart",

        "-shortest",

        output_path,
    ]

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
            "FFmpeg audio merge failed:\n"
            f"{exc.stderr}"
        ) from exc


def safe_delete(path: str):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as exc:
            print(
                f"Could not delete {path}: {exc}"
            )