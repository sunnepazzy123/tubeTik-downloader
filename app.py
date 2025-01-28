from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from middleware.index import setUpMiddlewares
from routes.index import router
from utils.config import mountStaticFolder  # Import the router


app = FastAPI()

setUpMiddlewares(app)

mountStaticFolder(app)

app.include_router(router)

# Redirect from the root (/) to the /tube-tik-downloader route
@app.get("/")
async def redirect_to_downloader():
    return RedirectResponse(url="/tube-tik-downloader")
