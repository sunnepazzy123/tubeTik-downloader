from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

mountFolders = [
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

def mountStaticFolders(app: FastAPI):
    for mount in mountFolders:
        path = mount['path']
        directory = mount['directory']
        mountName = mount['mountName']
        
        app.mount(path, StaticFiles(directory=directory), name=mountName)

