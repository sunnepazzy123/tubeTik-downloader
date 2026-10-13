import os
import uuid

from services.video_editor import (
    cut_segments,
    join_videos,
    zoom_video,
    reframe_vertical,
    remove_intro_outro,
    safe_delete,
    add_logo as add_logo_to_video,
)


def process_downloaded_video(
    input_path: str,
    output_dir: str,
    intro_seconds: float = 0,
    outro_seconds: float = 0,
    segments: list[tuple[float, float]] | None = None,
    zoom: float | None = None,
    vertical: bool = False,
    aspect_ratio: str = "original",
    quality: str = "balanced",
    output_name: str | None = None,
    add_logo: bool = False,
    logo_path: str | None = None,
) -> str:

    if not os.path.isfile(input_path):
        raise FileNotFoundError(
            f"Input video not found: {input_path}"
        )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    job_id = uuid.uuid4().hex

    current_path = input_path

    temporary_files: list[str] = []
    temporary_dirs: list[str] = []

    try:

        # ---------------------------------
        # 1. Trim intro / outro
        # ---------------------------------

        if intro_seconds > 0 or outro_seconds > 0:

            trimmed_path = os.path.join(
                output_dir,
                f"trimmed_{job_id}.mp4",
            )

            remove_intro_outro(
                input_path=current_path,
                output_path=trimmed_path,
                intro_seconds=intro_seconds,
                outro_seconds=outro_seconds,
            )

            current_path = trimmed_path

            temporary_files.append(
                trimmed_path
            )


        # ---------------------------------
        # 2. Keep selected segments
        # ---------------------------------

        if segments:

            segment_dir = os.path.join(
                output_dir,
                f"segments_{job_id}",
            )

            os.makedirs(
                segment_dir,
                exist_ok=True,
            )

            temporary_dirs.append(
                segment_dir
            )

            clips = cut_segments(
                input_path=current_path,
                segments=segments,
                output_dir=segment_dir,
            )

            if not clips:
                raise RuntimeError(
                    "No video segments were created."
                )

            joined_path = os.path.join(
                output_dir,
                f"joined_{job_id}.mp4",
            )

            join_videos(
                video_paths=clips,
                output_path=joined_path,
            )

            current_path = joined_path

            temporary_files.extend(
                clips
            )

            temporary_files.append(
                joined_path
            )


        # ---------------------------------
        # 3. Zoom
        # ---------------------------------

        if zoom is not None and zoom > 1:

            zoomed_path = os.path.join(
                output_dir,
                f"zoomed_{job_id}.mp4",
            )

            zoom_video(
                input_path=current_path,
                output_path=zoomed_path,
                zoom=zoom,
            )

            current_path = zoomed_path

            temporary_files.append(
                zoomed_path
            )


        # ---------------------------------
        # 4. Aspect ratio
        # ---------------------------------

        if vertical or aspect_ratio == "9:16":

            vertical_path = os.path.join(
                output_dir,
                f"vertical_{job_id}.mp4",
            )

            reframe_vertical(
                input_path=current_path,
                output_path=vertical_path,
            )

            current_path = vertical_path

            temporary_files.append(
                vertical_path
            )

        elif aspect_ratio in {
            "4:5",
            "1:1",
            "16:9",
        }:

            reframed_path = os.path.join(
                output_dir,
                f"reframed_{job_id}.mp4",
            )

            reframe_video(
                input_path=current_path,
                output_path=reframed_path,
                aspect_ratio=aspect_ratio,
                quality=quality,
            )

            current_path = reframed_path

            temporary_files.append(
                reframed_path
            )


        # ---------------------------------
        # 5. Add logo
        # ---------------------------------

        if add_logo:

            if not logo_path:
                raise ValueError(
                    "logo_path is required when add_logo=True"
                )

            if not os.path.isfile(
                logo_path
            ):
                raise FileNotFoundError(
                    f"Logo not found: {logo_path}"
                )

            logo_output_path = os.path.join(
                output_dir,
                f"logo_{job_id}.mp4",
            )

            add_logo_to_video(
                input_path=current_path,
                logo_path=logo_path,
                output_path=logo_output_path,
            )

            current_path = logo_output_path

            temporary_files.append(
                logo_output_path
            )


        # ---------------------------------
        # 6. Final output filename
        # ---------------------------------

        if output_name:

            safe_name = os.path.basename(
                output_name
            )

            safe_name = os.path.splitext(
                safe_name
            )[0]

            final_filename = (
                f"{safe_name}.mp4"
            )

        else:

            final_filename = (
                f"edited_{job_id}.mp4"
            )


        final_path = os.path.join(
            output_dir,
            final_filename,
        )


        # ---------------------------------
        # 7. Finalize file
        # ---------------------------------

        if current_path == input_path:

            copy_video(
                input_path=input_path,
                output_path=final_path,
            )

        else:

            if os.path.exists(
                final_path
            ):
                os.remove(
                    final_path
                )

            os.replace(
                current_path,
                final_path,
            )

            if current_path in temporary_files:
                temporary_files.remove(
                    current_path
                )


        if not os.path.isfile(
            final_path
        ):
            raise RuntimeError(
                "Final edited video was not created."
            )


        return final_path


    finally:

        # ---------------------------------
        # Remove temporary files
        # ---------------------------------

        for path in temporary_files:

            safe_delete(
                path
            )


        # ---------------------------------
        # Remove temporary folders
        # ---------------------------------

        for directory in temporary_dirs:

            safe_remove_directory(
                directory
            )

def copy_video(
    input_path: str,
    output_path: str,
):
    """
    Copy video without re-encoding.
    """

    import shutil

    shutil.copy2(
        input_path,
        output_path,
    )


def safe_remove_directory(
    directory: str,
):
    if not directory:
        return

    if not os.path.isdir(
        directory
    ):
        return

    try:
        # directory should normally
        # already be empty
        os.rmdir(
            directory
        )

    except OSError:
        # If something remains inside,
        # remove it safely.
        import shutil

        try:
            shutil.rmtree(
                directory
            )

        except Exception as exc:
            print(
                f"Could not delete directory "
                f"{directory}: {exc}"
            )