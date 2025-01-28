import os
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
import yt_dlp

from utils.index import delete_file, getTitle, setFormatTemplate

router = APIRouter()


@router.get("/tube-tik-downloader", response_class=HTMLResponse)
async def serve_index():
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@router.post("/tube-tik-downloader")
async def download_file(video_url: str = Form(...), format: str = Form(...), background_tasks: BackgroundTasks = None):
    save_dir = os.path.join(os.getcwd(), "downloads")  # Use current working directory
    os.makedirs(save_dir, exist_ok=True)  # Ensure the directory exists

    try:
        video_title = getTitle(video_url)

        base_name = os.path.join(save_dir, video_title)
        expected_file_path = f"{base_name}.{format}"

        ydl_opts = setFormatTemplate(base_name, format)
        # Download the file using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Check if the expected file exists
        if not os.path.exists(expected_file_path):
            raise FileNotFoundError(f"The file {expected_file_path} was not found after download.")

        # Serve the file
        media_type = "audio/mpeg" if format == "mp3" else "video/mp4"

        # Return the file as a downloadable response
        response = FileResponse(
            expected_file_path,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={video_title}.{format}"}
        )

        # Start the background task to delete the file after response is sent
        if background_tasks:
            background_tasks.add_task(delete_file, expected_file_path)

        return response

    except Exception as e:
        # Debugging error
        print(f"Error during download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
