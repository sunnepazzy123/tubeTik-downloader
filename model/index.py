# Define the Pydantic model
from pydantic import BaseModel


class DownloadRequest(BaseModel):
    video_url: str
    format: str