from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import torch
from pathlib import Path
import io
import torchvision
import os
from datetime import datetime
import asyncio
from typing import Optional

app = FastAPI()

# COCO 클래스 목록
CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
    'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
    'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
    'giraffe', 'target', 'umbrella', 'target', 'tie', 'suitcase', 'frisbee',
    'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
    'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
    'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
    'refrigerator', 'book', 'target', 'vase', 'scissors', 'teddy bear', 'hair drier',
    'toothbrush'
]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
YOLO_ROOT = Path.cwd()
model_path = YOLO_ROOT / 'yolov5n.pt'

SAVE_BACKBONE_PAYLOADS = os.getenv("SAVE_BACKBONE_PAYLOADS", "true").lower() in {"true", "1", "yes", "on"}
BACKBONE_PAYLOAD_DIR = Path(os.getenv("BACKBONE_PAYLOAD_DIR", "/data/backbone-inputs")).resolve()
payload_lock = asyncio.Lock()

if SAVE_BACKBONE_PAYLOADS:
    BACKBONE_PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _persist_backbone_payload(data: bytes, original_filename: Optional[str] = None) -> Optional[str]:
    if not SAVE_BACKBONE_PAYLOADS:
        return None

    suffix = Path(original_filename or "").suffix or ".pt"
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"backbone_{timestamp}{suffix}"
    target_path = BACKBONE_PAYLOAD_DIR / filename

    async with payload_lock:
        await asyncio.to_thread(target_path.write_bytes, data)

    return str(target_path)

# 전체 모델 로드 및 CUDA로 이동
print("전체 모델 로드 시작...")
full_model = torch.load(model_path, map_location=device, weights_only=False)['model'].float().eval().to(device)
print("전체 모델 로드 완료.")

# YAML 기준: backbone은 10개의 레이어 (인덱스 0~9)
backbone_len = 10
head_layers = full_model.model[backbone_len:]
print(f"head_layers (인덱스 {backbone_len} 이후) 로드 완료.")

def head_forward(layers, backbone_outputs):
    """
    YOLOv5 네크+헤드 forward 함수.
    backbone_outputs는 백본에서 반환된 리스트 (인덱스 0~9).
    """
    outputs = backbone_outputs.copy()  # 기존 백본 출력들을 복사
    x = outputs[-1]  # 백본의 마지막 출력 (인덱스 9)
    print(f"백본 마지막 출력 shape: {x.shape}")
    for idx, m in enumerate(layers, start=backbone_len):
        if m.f != -1:
            if isinstance(m.f, int):
                x = outputs[m.f]
            else:
                x = [outputs[j] for j in m.f]
        x = m(x)
        outputs.append(x)
        print(f"레이어 {idx} 통과 후 출력 shape: {x.shape if hasattr(x, 'shape') else x}")
    return outputs[-1]

@app.post("/process_neck_head")
async def process_backbone(file: UploadFile = File(...)):
    print("fastapi 들어옴")
    contents = await file.read()
    saved_path = await _persist_backbone_payload(contents, file.filename)
    buffer = io.BytesIO(contents)
    backbone_outputs = torch.load(buffer, map_location=device)
    print(f"불러온 백본 출력 개수: {len(backbone_outputs)}, 마지막 출력 shape: {backbone_outputs[-1].shape}")

    with torch.no_grad():
        head_output = head_forward(head_layers, backbone_outputs)
        # Detect 모듈이 튜플을 반환하는 경우, 첫 번째 요소 사용
        if isinstance(head_output, tuple):
            head_output = head_output[0]

    # head_output의 shape: [1, num_dets, 85]
    #   0:4 -> [cx, cy, w, h]
    #   4   -> obj_conf
    #   5:  -> class_scores
    pred = head_output.squeeze(0)  # [num_dets, 85]

    # 1) confidence 필터링 (obj_conf)
    conf_thres = 0.20
    mask = pred[:, 4] > conf_thres
    filtered = pred[mask]  # [N, 85]
    print(f"필터링 후 검출 개수: {filtered.shape[0]}")

    # 2) center xywh -> xyxy 변환
    cxcywh = filtered[:, :4]
    obj_conf = filtered[:, 4:5]
    class_scores = filtered[:, 5:]
    class_conf, class_id = class_scores.max(dim=1)   # 각 row별 최대 class score 및 index
    final_scores = obj_conf.squeeze() * class_conf   # 최종 score = obj_conf * class_conf

    # center to xyxy
    x1 = cxcywh[:, 0] - cxcywh[:, 2] / 2
    y1 = cxcywh[:, 1] - cxcywh[:, 3] / 2
    x2 = cxcywh[:, 0] + cxcywh[:, 2] / 2
    y2 = cxcywh[:, 1] + cxcywh[:, 3] / 2
    boxes_xyxy = torch.stack([x1, y1, x2, y2], dim=1)  # [N, 4]

    # 3) NMS 적용
    iou_threshold = 0.45
    keep_idx = torchvision.ops.nms(boxes_xyxy, final_scores, iou_threshold)
    boxes_xyxy = boxes_xyxy[keep_idx]
    final_scores = final_scores[keep_idx]
    class_id = class_id[keep_idx]

    # 4) 최종 detection 구성
    detections = []
    for i in range(len(keep_idx)):
        x1, y1, x2, y2 = boxes_xyxy[i].tolist()
        label_idx = int(class_id[i].item())
        score_val = final_scores[i].item()
        label = CLASSES[label_idx] if label_idx < len(CLASSES) else f"Unknown({label_idx})"

        detection = {
            "box": [x1, y1, x2, y2],
            "class": label,
            "confidence": score_val
        }
        detections.append(detection)
        print(f"[#{i}] {detection}")

    response_payload = {"detections": detections}
    if saved_path:
        response_payload["saved_path"] = saved_path

    # JSON으로 반환
    return JSONResponse(content=response_payload)
