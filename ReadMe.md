# TubeTik Downloader

## **Overview**
This project is built using the **FastApi** framework and follows a modular architecture.


## **Dependencies**
- [ffmpeg](#ffmpeg)
- [python](#python)
- [uvicorn](#uvicorn)
- [docker](#docker)

### Clone Repo
```
  git clone <repo-name>
```

#### ***Run app using Docker***
The default port is localhost:8000 after running the command below
```
  docker compose up -d
```
after containers are up and running, check the app and API Docs
- http://localhost:8000
- http://localhost:8000/docs#/


#### ***Run app locally***
### Install Dependencies
```
pip install --no-cache-dir -r requirements.txt
```
```
  uvicorn app:app --reload
```

