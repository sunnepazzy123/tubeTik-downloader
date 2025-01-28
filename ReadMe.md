# TubeTik Downloader

## **Overview**
This project is built using the **FastApi** framework and follows a modular architecture.


## **Dependencies**
- [ffmpeg](#ffmpeg)
- [python](#python)
- [uvicorn](#uvicorn)
- [docker](#docker)

### Install Dependencies
```
pip install --no-cache-dir -r requirements.txt
```

#### **Docker Approach**
The default port is localhost:8000 after running the command below
```
  git clone <repo-name>
```
```
  docker compose up -d
```
after containers are up and running, check the API Docs
http://localhost:8000/docs#/

#### **Run app locally*
```
  uvicorn app:app --reload
```

