from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

mountFolder = [
    {
        "path": "/static",
        "directory": "static",
        "mountName": "static"
    },
    {
        "path": "/downloads",
        "directory": "downloads",
        "mountName": "downloads"
    },
]

def mountStaticFolder(app: FastAPI):
    for mount in mountFolder:
        path = mount['path']
        directory = mount['directory']
        mountName = mount['mountName']
        
        app.mount(path, StaticFiles(directory=directory), name=mountName)

