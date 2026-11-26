import json
import math
import os
import re
import tempfile
from datetime import datetime
from typing import Any

import yt_dlp

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import (
    FileResponse,
    HTMLResponse,
)

from services.video_processor import (
    process_downloaded_video,
)

from services.audio_editor import (
    AUDIO_EXTENSIONS,
    cut_audio_file,
)


router = APIRouter()

download_progress: dict[str, dict[str, Any]] = {}


# ------------------------------------------
# Helpers
# ------------------------------------------

def get_download_dir() -> str:

    download_dir = os.path.join(
        os.getcwd(),
        "downloads",
    )

    os.makedirs(
        download_dir,
        exist_ok=True,
    )

    return download_dir


def format_file_size(
    size: int,
) -> str:

    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return (
            f"{size / 1024:.1f} KB"
        )

    if size < 1024 * 1024 * 1024:
        return (
            f"{size / (1024 * 1024):.1f} MB"
        )

    return (
        f"{size / (1024 * 1024 * 1024):.2f} GB"
    )


def validate_logo_extension(
    filename: str,
) -> str:

    extension = (
        os.path.splitext(
            filename
        )[1]
        .lower()
    )

    allowed = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }

    if extension not in allowed:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported logo format. "
                "Use PNG, JPG, JPEG or WEBP."
            ),
        )

    return extension


def is_youtube_url(
    url: str,
) -> bool:

    normalized_url = url.lower()

    return (
        "youtube.com" in normalized_url
        or "youtu.be" in normalized_url
    )


def sanitize_filename(
    filename: str,
) -> str:

    filename = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "",
        filename,
    )

    filename = filename.strip(
        " ."
    )

    if not filename:
        filename = "download"

    return filename[:180]


def parse_segments_json(
    segments: str | None,
) -> list[tuple[float, float]] | None:
    """
    Parse a JSON list of [start, end] pairs (in seconds),
    e.g. "[[0, 20], [30, 45]]".
    """

    if not segments:
        return None

    try:

        decoded = json.loads(
            segments
        )

        if not isinstance(
            decoded,
            list,
        ):

            raise ValueError(
                "Segments must be a list"
            )

        parsed_segments = []

        for item in decoded:

            if (
                not isinstance(
                    item,
                    list,
                )
                or len(
                    item
                ) != 2
            ):

                raise ValueError(
                    "Invalid segment"
                )

            start = float(
                item[0]
            )

            end = float(
                item[1]
            )

            if (
                not math.isfinite(start)
                or not math.isfinite(end)
                or start < 0
                or end <= start
            ):

                raise ValueError(
                    (
                        "Invalid segment: "
                        f"{start}-{end}"
                    )
                )

            parsed_segments.append(
                (
                    start,
                    end,
                )
            )

        return parsed_segments

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid segments: "
                f"{str(exc)}"
            ),
        )


# ------------------------------------------
# YouTube / yt-dlp configuration
# ------------------------------------------

def add_youtube_options(
    ydl_opts: dict,
    video_url: str,
) -> dict:

    if not is_youtube_url(
        video_url
    ):
        return ydl_opts

    # Use Chrome's logged-in YouTube session.
    ydl_opts["cookiesfrombrowser"] = (
        "chrome",
    )

    # Equivalent to:
    # --js-runtimes node
    ydl_opts["js_runtimes"] = {
        "node": {}
    }

    # This is the combination that worked
    # successfully from the terminal:
    #
    # --extractor-args
    # "youtube:player_client=default,web_embedded"
    ydl_opts["extractor_args"] = {
        "youtube": {
            "player_client": [
                "default",
                "web_embedded",
            ]
        }
    }

    return ydl_opts


def get_metadata_options(
    video_url: str,
) -> dict:

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    return add_youtube_options(
        ydl_opts,
        video_url,
    )


def get_video_title(
    video_url: str,
) -> str:

    ydl_opts = get_metadata_options(
        video_url
    )

    with yt_dlp.YoutubeDL(
        ydl_opts
    ) as ydl:

        info = ydl.extract_info(
            video_url,
            download=False,
        )

    title = (
        info.get("title")
        or info.get("id")
        or "download"
    )

    return sanitize_filename(
        title
    )


def get_format_options(
    base_name: str,
    output_format: str,
) -> dict:

    output_format = output_format.lower()

    # ----------------------------------
    # MP3
    # ----------------------------------

    if output_format == "mp3":

        return {
            "format":
                "bestaudio/best",

            "outtmpl":
                f"{base_name}.%(ext)s",

            "postprocessors": [
                {
                    "key":
                        "FFmpegExtractAudio",

                    "preferredcodec":
                        "mp3",

                    "preferredquality":
                        "192",
                }
            ],
        }

    # ----------------------------------
    # MP4
    # ----------------------------------

    if output_format == "mp4":

        return {
            # Prefer MP4-compatible streams first.
            # Fall back to any available streams.
            "format": (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                "/bestvideo+bestaudio"
                "/best"
            ),

            "outtmpl":
                f"{base_name}.%(ext)s",

            # Force merged result to MP4.
            "merge_output_format":
                "mp4",

            # Remux final output to MP4 when needed.
            "postprocessors": [
                {
                    "key":
                        "FFmpegVideoRemuxer",

                    "preferedformat":
                        "mp4",
                }
            ],
        }

    raise HTTPException(
        status_code=400,
        detail=(
            f"Unsupported format: {output_format}. "
            "Use mp4 or mp3."
        ),
    )


def find_downloaded_file(
    base_name: str,
    output_format: str,
) -> str:

    expected_file = (
        f"{base_name}.{output_format}"
    )

    if os.path.isfile(
        expected_file
    ):
        return expected_file

    directory = os.path.dirname(
        base_name
    )

    base_filename = os.path.basename(
        base_name
    )

    for filename in os.listdir(
        directory
    ):

        file_path = os.path.join(
            directory,
            filename,
        )

        if not os.path.isfile(
            file_path
        ):
            continue

        if not filename.startswith(
            base_filename
        ):
            continue

        extension = (
            os.path.splitext(
                filename
            )[1]
            .lower()
        )

        if (
            output_format == "mp4"
            and extension == ".mp4"
        ):
            return file_path

        if (
            output_format == "mp3"
            and extension == ".mp3"
        ):
            return file_path

    raise FileNotFoundError(
        (
            "Download completed but the "
            f"final {output_format} file "
            "could not be found."
        )
    )


# ------------------------------------------
# FRONTEND
# ------------------------------------------

@router.get(
    "/tube-tik-downloader",
    response_class=HTMLResponse,
)
async def serve_index():

    with open(
        "index.html",
        "r",
        encoding="utf-8",
    ) as f:

        return HTMLResponse(
            content=f.read(),
            status_code=200,
        )


# ------------------------------------------
# PROGRESS
# ------------------------------------------

@router.get(
    "/tube-tik-downloader/progress/{download_id}"
)
async def get_download_progress(
    download_id: str,
):

    return download_progress.get(
        download_id,
        {
            "percent": 0,
            "status": "waiting",
        },
    )


# ------------------------------------------
# DOWNLOAD VIDEO
# ------------------------------------------

@router.post(
    "/tube-tik-downloader"
)
async def download_file(

    video_url: str =
        Form(...),

    format: str =
        Form(...),

    download_id: str =
        Form(...),

):

    save_dir = get_download_dir()

    output_format = (
        format
        .strip()
        .lower()
    )

    try:

        download_progress[
            download_id
        ] = {
            "percent": 0,
            "status": "starting",
        }

        # ----------------------------------
        # Get title using the SAME
        # YouTube authentication config.
        # ----------------------------------

        video_title = get_video_title(
            video_url
        )

        base_name = os.path.join(
            save_dir,
            video_title,
        )

        # ----------------------------------
        # Progress hook
        # ----------------------------------

        def progress_hook(
            data: dict,
        ):

            status = data.get(
                "status"
            )

            if status == "downloading":

                downloaded_bytes = data.get(
                    "downloaded_bytes",
                    0,
                )

                total_bytes = (
                    data.get(
                        "total_bytes"
                    )
                    or data.get(
                        "total_bytes_estimate"
                    )
                    or 0
                )

                if total_bytes > 0:

                    percent = int(
                        (
                            downloaded_bytes
                            / total_bytes
                        )
                        * 100
                    )

                    percent = max(
                        0,
                        min(
                            percent,
                            99,
                        ),
                    )

                    download_progress[
                        download_id
                    ] = {
                        "percent":
                            percent,

                        "status":
                            "downloading",
                    }

            elif status == "finished":

                download_progress[
                    download_id
                ] = {
                    "percent": 99,
                    "status": "processing",
                }

        # ----------------------------------
        # Build format options
        # ----------------------------------

        ydl_opts = get_format_options(
            base_name,
            output_format,
        )

        # ----------------------------------
        # Add YouTube-specific settings
        # ----------------------------------

        ydl_opts = add_youtube_options(
            ydl_opts,
            video_url,
        )

        # ----------------------------------
        # Add progress callback
        # ----------------------------------

        ydl_opts[
            "progress_hooks"
        ] = [
            progress_hook
        ]

        # ----------------------------------
        # Download
        # ----------------------------------

        with yt_dlp.YoutubeDL(
            ydl_opts
        ) as ydl:

            ydl.download(
                [
                    video_url
                ]
            )

        # ----------------------------------
        # Find final processed output
        # ----------------------------------

        final_file_path = find_downloaded_file(
            base_name,
            output_format,
        )

        download_progress[
            download_id
        ] = {
            "percent": 100,
            "status": "completed",
        }

        media_type = (
            "audio/mpeg"
            if output_format == "mp3"
            else "video/mp4"
        )

        return FileResponse(
            final_file_path,

            media_type=
                media_type,

            filename=
                os.path.basename(
                    final_file_path
                ),
        )

    except HTTPException:

        download_progress[
            download_id
        ] = {
            "percent": 0,
            "status": "failed",
        }

        raise

    except Exception as exc:

        print(
            (
                "Download failed: "
                f"{exc}"
            )
        )

        download_progress[
            download_id
        ] = {
            "percent": 0,
            "status": "failed",
            "error": str(exc),
        }

        raise HTTPException(
            status_code=500,
            detail=str(
                exc
            ),
        )


# ------------------------------------------
# LIST FILES
# ------------------------------------------

@router.get(
    "/tube-tik-downloader/files"
)
async def list_downloaded_files():

    download_dir = get_download_dir()

    files = []

    for filename in os.listdir(
        download_dir
    ):

        file_path = os.path.join(
            download_dir,
            filename,
        )

        if not os.path.isfile(
            file_path
        ):
            continue

        extension = (
            os.path.splitext(
                filename
            )[1]
            .lower()
        )

        if extension in {
            ".mp4",
            ".mov",
            ".mkv",
            ".webm",
        }:

            file_type = "video"

        elif extension in AUDIO_EXTENSIONS:

            file_type = "audio"

        else:

            file_type = "file"

        stat = os.stat(
            file_path
        )

        files.append(
            {
                "name":
                    filename,

                "type":
                    file_type,

                "size":
                    format_file_size(
                        stat.st_size
                    ),

                "size_bytes":
                    stat.st_size,

                "modified":
                    datetime.fromtimestamp(
                        stat.st_mtime
                    ).strftime(
                        "%Y-%m-%d %H:%M"
                    ),

                "modified_timestamp":
                    stat.st_mtime,
            }
        )

    files.sort(
        key=lambda item:
            item[
                "modified_timestamp"
            ],
        reverse=True,
    )

    return {
        "files":
            files
    }


# ------------------------------------------
# DOWNLOAD EXISTING FILE
# ------------------------------------------

@router.get(
    "/tube-tik-downloader/files/{filename}"
)
async def download_existing_file(
    filename: str,
):

    safe_filename = os.path.basename(
        filename
    )

    file_path = os.path.join(
        get_download_dir(),
        safe_filename,
    )

    if not os.path.isfile(
        file_path
    ):

        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    extension = (
        os.path.splitext(
            safe_filename
        )[1]
        .lower()
    )

    media_type = None

    if extension == ".mp4":
        media_type = "video/mp4"

    elif extension == ".mp3":
        media_type = "audio/mpeg"

    return FileResponse(
        file_path,
        media_type=
            media_type,
        filename=
            safe_filename,
    )


# ------------------------------------------
# DELETE
# ------------------------------------------

@router.delete(
    "/tube-tik-downloader/files/{filename}"
)
async def delete_downloaded_file(
    filename: str,
):

    safe_filename = os.path.basename(
        filename
    )

    file_path = os.path.join(
        get_download_dir(),
        safe_filename,
    )

    if not os.path.isfile(
        file_path
    ):

        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    os.remove(
        file_path
    )

    return {
        "success": True,
        "filename":
            safe_filename,
    }


# ------------------------------------------
# EDIT VIDEO + OPTIONAL LOGO
# ------------------------------------------

@router.post(
    "/tube-tik-downloader/edit"
)
async def edit_downloaded_video(

    file_name: str =
        Form(...),

    intro_seconds: float =
        Form(0),

    outro_seconds: float =
        Form(0),

    segments: str | None =
        Form(None),

    zoom: float | None =
        Form(None),

    aspect_ratio: str =
        Form(
            "original"
        ),

    vertical: bool =
        Form(False),

    quality: str =
        Form(
            "balanced"
        ),

    output_name: str | None =
        Form(None),

    logo: UploadFile | None =
        File(None),

):

    download_dir = get_download_dir()

    safe_filename = os.path.basename(
        file_name
    )

    input_path = os.path.join(
        download_dir,
        safe_filename,
    )

    if not os.path.isfile(
        input_path
    ):

        raise HTTPException(
            status_code=404,
            detail=
                "Video file not found",
        )

    # ----------------------------------
    # Parse segments JSON
    # ----------------------------------

    parsed_segments = parse_segments_json(
        segments
    )

    # ----------------------------------
    # Save uploaded logo temporarily
    # ----------------------------------

    logo_path = None

    try:

        if logo is not None:

            extension = validate_logo_extension(
                logo.filename or ""
            )

            logo_content = await logo.read()

            if not logo_content:

                raise HTTPException(
                    status_code=400,
                    detail=
                        "Uploaded logo is empty.",
                )

            # 10 MB logo limit
            max_logo_size = (
                10
                * 1024
                * 1024
            )

            if (
                len(
                    logo_content
                )
                >
                max_logo_size
            ):

                raise HTTPException(
                    status_code=400,
                    detail=
                        "Logo must be smaller than 10 MB.",
                )

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=extension,
            ) as temp_file:

                temp_file.write(
                    logo_content
                )

                logo_path = (
                    temp_file.name
                )

        # ----------------------------------
        # Process video
        # ----------------------------------

        final_path = process_downloaded_video(

            input_path=
                input_path,

            output_dir=
                download_dir,

            intro_seconds=
                intro_seconds,

            outro_seconds=
                outro_seconds,

            segments=
                parsed_segments,

            zoom=
                zoom,

            vertical=
                vertical,

            aspect_ratio=
                aspect_ratio,

            quality=
                quality,

            output_name=
                output_name,

            add_logo=
                logo_path
                is not None,

            logo_path=
                logo_path,

        )

        if not os.path.isfile(
            final_path
        ):

            raise RuntimeError(
                (
                    "Video processor did "
                    "not create the final file."
                )
            )

        return FileResponse(
            final_path,

            media_type=
                "video/mp4",

            filename=
                os.path.basename(
                    final_path
                ),
        )

    except HTTPException:

        raise

    except Exception as exc:

        print(
            (
                "Video edit failed: "
                f"{exc}"
            )
        )

        raise HTTPException(
            status_code=500,
            detail=str(
                exc
            ),
        )

    finally:

        # ----------------------------------
        # Remove temporary logo
        # ----------------------------------

        if (
            logo_path
            and os.path.isfile(
                logo_path
            )
        ):

            try:

                os.remove(
                    logo_path
                )

            except OSError as exc:

                print(
                    (
                        "Could not remove "
                        "temporary logo: "
                        f"{exc}"
                    )
                )


# ------------------------------------------
# EDIT AUDIO (CUT / KEEP PORTIONS -> MP3)
# ------------------------------------------

# Plain `def` so FastAPI runs the blocking
# ffmpeg call in its threadpool instead of
# stalling the event loop.
@router.post(
    "/tube-tik-downloader/edit-audio"
)
def edit_downloaded_audio(

    file_name: str =
        Form(...),

    # JSON list of [start, end] pairs in
    # seconds, e.g. "[[30, 75], [120, 150]]".
    # Portions are joined in this order.
    segments: str =
        Form(...),

    output_name: str | None =
        Form(None),

):

    download_dir = get_download_dir()

    safe_filename = os.path.basename(
        file_name
    )

    input_path = os.path.join(
        download_dir,
        safe_filename,
    )

    if not os.path.isfile(
        input_path
    ):

        raise HTTPException(
            status_code=404,
            detail=
                "Audio file not found",
        )

    extension = (
        os.path.splitext(
            safe_filename
        )[1]
        .lower()
    )

    if extension not in AUDIO_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported audio format. "
                "Use MP3, WAV, AAC or M4A."
            ),
        )

    parsed_segments = parse_segments_json(
        segments
    )

    if not parsed_segments:

        raise HTTPException(
            status_code=400,
            detail=
                "Add at least one portion to keep.",
        )

    clean_output_name = (
        sanitize_filename(
            output_name
        )
        if output_name
        and output_name.strip()
        else None
    )

    try:

        final_path = cut_audio_file(

            input_path=
                input_path,

            output_dir=
                download_dir,

            segments=
                parsed_segments,

            output_name=
                clean_output_name,

        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        )

    except Exception as exc:

        print(
            (
                "Audio edit failed: "
                f"{exc}"
            )
        )

        raise HTTPException(
            status_code=500,
            detail=str(
                exc
            ),
        )

    return FileResponse(
        final_path,

        media_type=
            "audio/mpeg",

        filename=
            os.path.basename(
                final_path
            ),
    )