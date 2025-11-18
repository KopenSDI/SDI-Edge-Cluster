# fastapi_image_stream_server.py
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import time
import os
from pathlib import Path
from datetime import datetime
import asyncio
from typing import Optional

app = FastAPI()


app.mount("/static", StaticFiles(directory="."), name="static")

latest_frame = None
save_lock = asyncio.Lock()

SAVE_IMAGES = os.getenv("SAVE_UPLOADED_IMAGES", "true").lower() in {"true", "1", "yes", "on"}
SAVE_DIR = Path(os.getenv("UPLOADED_IMAGE_DIR", "/data/uploaded-images")).resolve()
if SAVE_IMAGES:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


async def _persist_image(image_bytes: bytes, original_filename: Optional[str] = None) -> Optional[str]:
    if not SAVE_IMAGES:
        return None

    suffix = Path(original_filename or "").suffix or ".jpg"
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"frame_{timestamp}{suffix}"
    target_path = SAVE_DIR / filename

    async with save_lock:
        await asyncio.to_thread(target_path.write_bytes, image_bytes)

    return str(target_path)


@app.post("/upload_image")
async def upload_image(file: UploadFile = File(...)):
    global latest_frame
    latest_frame = await file.read()
    saved_path = await _persist_image(latest_frame, file.filename)
    response = {"message": "Image received"}
    if saved_path:
        response["saved_path"] = saved_path
    return response

def frame_generator():
    global latest_frame

    while True:
        if latest_frame is not None:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + latest_frame + b"\r\n")
        time.sleep(0.05) 

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/", response_class=HTMLResponse)
def index():
    html_content = """
    <html>
        <head>
            <title>SDR(TURTLEBOT) Video</title>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    background: #2c3e50; /* 어두운 배경 */
                    color: #ecf0f1;
                    font-family: Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: flex-start;
                    min-height: 100vh;
                }
                .header {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    margin-top: 20px;
                }
                .header img {
                    height: 80px;
                    margin-bottom: 10px;
                    /* 투명 이미지이므로 blend 관련 스타일 제거 */
                }
                .header h1 {
                    font-size: 26px;
                    margin: 0;
                    font-weight: 600;
                    text-align: center;
                }
                .video-container {
                    margin-top: 30px;
                    border: 5px solid #34495e;
                    box-shadow: 0px 0px 20px rgba(0, 0, 0, 0.5);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }
                .video-container img {
                    display: block;
                    max-width: 100%;
                    height: auto;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <img src="/static/keti_logo_real.png" alt="KETI Logo">
                <h1>SDR(TURTLEBOT)-REALTIME-VIDEO</h1>
            </div>
            <div class="video-container">
                <img src="/video_feed" alt="Real-time Video Feed">
            </div>
        </body>
    </html>
    """
    return html_content
