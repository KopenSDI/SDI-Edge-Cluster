import os
import torch
import torchvision.transforms as T
import cv2
from pathlib import Path
import requests
import io
import time
from datetime import datetime


# BackboneModel 클래스 정의 (저장할 때 사용한 클래스)
class BackboneModel(torch.nn.Module):
    def __init__(self, layers):
        super(BackboneModel, self).__init__()
        self.layers = torch.nn.ModuleList(layers)

    def forward(self, x):
        outputs = []
        for m in self.layers:
            if m.f != -1:
                if isinstance(m.f, int):
                    x = outputs[m.f]
                else:
                    x = [outputs[j] for j in m.f]
            x = m(x)
            outputs.append(x)
        return outputs


# 경로 설정
YOLO_ROOT = Path.cwd()
backbone_model_path = YOLO_ROOT / 'yolov5n_backbone.pt'

# 안전한 globals를 추가하여 분할한 backbone 모델 로드 (weights_only=False 옵션 사용)
with torch.serialization.safe_globals({"__main__.BackboneModel": BackboneModel}):
    backbone_model = torch.load(backbone_model_path, map_location='cpu', weights_only=False).eval()

# 이미지 전처리 transform 정의
transform = T.Compose([T.ToTensor()])

# 서버 연결 정보 (환경 변수 우선, 없으면 기본값 사용)
default_host = "10.0.5.56"
target_host = os.environ.get("BACKBONE_SERVER_HOST", default_host)

process_url = os.environ.get(
    "BACKBONE_NECK_HEAD_URL",
    f"http://{target_host}:30080/process_neck_head"
)

FASTAPI_SERVER_URL = os.environ.get(
    "BACKBONE_FASTAPI_URL",
    f"http://{os.environ.get('BACKBONE_FASTAPI_HOST', target_host)}:8000/upload_image"
)

SAVE_INPUT_IMAGES = os.environ.get("SAVE_INPUT_IMAGES", "true").lower() in {"true", "1", "yes", "on"}
INPUT_IMAGE_SAVE_DIR = Path(os.environ.get("INPUT_IMAGE_SAVE_DIR", "/data/backbone-input-images")).resolve()

if SAVE_INPUT_IMAGES:
    INPUT_IMAGE_SAVE_DIR.mkdir(parents=True, exist_ok=True)

# 웹캠 열기 (기본 카메라 장치 0번 사용)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("카메라를 열 수 없습니다.")

print("실시간 카메라 스트림 시작 (0.5초마다 neck-head 서버 전송, 20fps로 FastAPI 서버에 이미지 전송)")

last_process_time = 0
detections = []  # 마지막 서버 전송에서 받은 검출 결과

while True:
    # 프레임 획득
    ret, frame = cap.read()
    if not ret:
        print("프레임을 읽어올 수 없습니다.")
        break

    # 프레임을 640x640 크기로 resize하여 frame_resized에 저장
    frame_resized = cv2.resize(frame, (640, 640))

    # BGR -> RGB 변환 및 tensor 변환
    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
    input_tensor = transform(frame_rgb).unsqueeze(0)  # [1, 3, 640, 640]

    # Backbone 추론 (실시간으로 진행)
    with torch.no_grad():
        backbone_outputs = backbone_model(input_tensor)


    current_time = time.time()
    if current_time - last_process_time >= 0.5:
        last_process_time = current_time
        if SAVE_INPUT_IMAGES:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
            image_filename = INPUT_IMAGE_SAVE_DIR / f"frame_{timestamp}.jpg"
            if cv2.imwrite(str(image_filename), frame_resized):
                print(f"입력 이미지 저장: {image_filename}")
            else:
                print("입력 이미지 저장 실패")
        # 백본 출력 리스트를 메모리 버퍼에 저장 (바이너리 형식)
        buffer = io.BytesIO()
        torch.save(backbone_outputs, buffer)
        buffer.seek(0)
        data_bytes = buffer.getvalue()
        data_size = len(data_bytes)
        print(f"전송 데이터 크기: {data_size} 바이트")

        try:
            files = {"file": ("backbone_outputs.pt", data_bytes)}
            response = requests.post(process_url, files=files, timeout=5)
            resp_json = response.json()
            detections = resp_json.get("detections", [])
            print("neck-head 서버 응답:", detections)
        except Exception as e:
            print("neck-head 서버 요청 실패:", e)
            detections = []

    # 프레임에 검출 결과 그리기 (최근 neck-head 서버 결과 사용)
    frame_draw = frame_resized.copy()  # BGR 이미지
    for det in detections:
        box = det["box"]
        label = det["class"]
        conf = det["confidence"]
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(frame_draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame_draw,
            f"{label} {conf:.2f}",
            (x1, max(y1 - 10, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2
        )

    # 0.05초 간격 (약 20fps)로 FastAPI 서버에 이미지 전송
    ret2, jpeg = cv2.imencode('.jpg', frame_draw)
    if ret2:
        image_bytes = jpeg.tobytes()
        try:
            files = {"file": ("latest.jpg", image_bytes, "image/jpeg")}
            response = requests.post(FASTAPI_SERVER_URL, files=files, timeout=2)
            if response.status_code == 200:
                print("FastAPI 서버에 이미지 전송 성공")
            else:
                print("FastAPI 서버에 이미지 전송 실패:", response.status_code)
        except Exception as e:
            print("FastAPI 서버 요청 실패:", e)

    time.sleep(0.05)  # 약 20fps로 전송

cap.release()
