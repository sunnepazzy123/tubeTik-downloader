# Function to delete the file in the background after sending the response
import os

import yt_dlp

def delete_file(file_path: str):
    try:
        # Delete the file after sending the response
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File {file_path} deleted.")
        else:
            print(f"File {file_path} not found.")
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")
        
        
def setFormatTemplate(basename: str, format: str):
    ydl_opts = None
    if format == "mp3":
        # Configure yt-dlp options for MP3
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": basename,  # Base name without extension
            # 'outtmpl': f'{basename}-/%(title)s.%(ext)s',            # Save file with the title as filename
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "noplaylist": True,  # Ensure it's not a playlist download
        }
    else:  # For MP4 format
        ydl_opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best',  # Download the best video and audio
            'merge_output_format': 'mp4',                         # Ensure the final output is in MP4 format
            # 'outtmpl': f'{basename}-/%(title)s.%(ext)s',            # Save file with the title as filename
            "outtmpl": basename,  # Base name without extension
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',                       # Convert to MP4 if not already
            }],
            'postprocessor_args': [
                '-c:a', 'aac',                                  # Use AAC codec for audio
                '-b:a', '128k'                                  # Set audio bitrate to 128k
            ],
            'noplaylist': True,                                  # Only download single video, not a playlist
        }

    return ydl_opts


def getTitle(video_url: str):
        video_title = None
        # Get video info and extract the title
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            video_title = info_dict.get("title", "unknown").replace(" ", "_").replace("/", "_")  # Sanitize title
            
        return video_title
