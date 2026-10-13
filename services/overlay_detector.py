from services.video_cleaner import clean_video_overlays_auto

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([video_url])

final_file_path = clean_video_overlays_auto(
    expected_file_path
)