import os

from services.video_editor import (
    get_video_duration as get_media_duration,
    run_ffmpeg,
    safe_delete,
)


AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".aac",
    ".m4a",
}

# Keep generated names well under the usual 255-byte filename limit,
# even for titles full of multi-byte characters (emoji, CJK, ...).
MAX_STEM_BYTES = 200


def cut_audio(
    input_path: str,
    output_path: str,
    segments: list[tuple[float, float]],
):
    """
    Keep only the given (start, end) portions of an audio file,
    joined in the order supplied, and encode the result as MP3.
    """
    if not segments:
        raise ValueError("At least one segment is required")

    filters = []
    labels = []

    for index, (start, end) in enumerate(segments):
        label = f"[a{index}]"

        filters.append(
            f"[0:a]atrim=start={start:.3f}:end={end:.3f},"
            f"asetpts=PTS-STARTPTS{label}"
        )

        labels.append(label)

    filters.append(
        f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,

        "-filter_complex", ";".join(filters),
        "-map", "[out]",

        # Keep title / artist tags from the source.
        "-map_metadata", "0",

        "-c:a", "libmp3lame",
        "-q:a", "0",
        "-id3v2_version", "3",

        output_path,
    ]

    run_ffmpeg(command)

    return output_path


def cut_audio_file(
    input_path: str,
    output_dir: str,
    segments: list[tuple[float, float]],
    output_name: str | None = None,
) -> str:
    """
    Cut the requested portions out of input_path and save them as a
    new MP3 in output_dir. Never overwrites an existing file.
    Returns the path of the created file.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(
            f"Input audio not found: {input_path}"
        )

    if not segments:
        raise ValueError("Add at least one portion to keep.")

    duration = get_media_duration(input_path)

    clamped_segments = []

    for start, end in segments:
        if start >= duration:
            raise ValueError(
                f"Portion {format_seconds(start)}-{format_seconds(end)} "
                f"starts after the end of the audio "
                f"({format_seconds(duration)})."
            )

        clamped_segments.append(
            (start, min(end, duration))
        )

    if output_name:
        stem = os.path.splitext(
            os.path.basename(output_name)
        )[0]
    else:
        input_stem = os.path.splitext(
            os.path.basename(input_path)
        )[0]

        stem = f"{input_stem}_cut"

    final_path = unique_output_path(
        output_dir,
        truncate_utf8(stem, MAX_STEM_BYTES),
        ".mp3",
    )

    try:
        cut_audio(
            input_path=input_path,
            output_path=final_path,
            segments=clamped_segments,
        )
    except Exception:
        safe_delete(final_path)
        raise

    if not os.path.isfile(final_path):
        raise RuntimeError("Cut audio file was not created.")

    return final_path


def unique_output_path(
    output_dir: str,
    stem: str,
    extension: str,
) -> str:
    candidate = os.path.join(
        output_dir,
        f"{stem}{extension}",
    )

    counter = 2

    while os.path.exists(candidate):
        candidate = os.path.join(
            output_dir,
            f"{stem} ({counter}){extension}",
        )

        counter += 1

    return candidate


def truncate_utf8(
    text: str,
    max_bytes: int,
) -> str:
    encoded = text.encode("utf-8")

    if len(encoded) <= max_bytes:
        return text

    return encoded[:max_bytes].decode(
        "utf-8",
        errors="ignore",
    )


def format_seconds(
    seconds: float,
) -> str:
    minutes, secs = divmod(round(seconds, 1), 60)

    return f"{int(minutes)}:{secs:04.1f}"
