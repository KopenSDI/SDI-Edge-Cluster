# 빌드 스테이지: 필요한 시스템 라이브러리 설치 및 가상환경 설정
FROM python:3.12-slim as builder

# 필수 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 코드와 requirements만 복사 (필요한 경우, 추가 파일은 COPY . . 사용)
COPY requirements.txt .

# 가상환경 생성 및 pip 업그레이드
RUN python -m pip install --upgrade pip \
    && python -m venv /venv

# 가상환경의 pip를 이용해 의존성 설치
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt



# 최종 스테이지: 실행에 필요한 파일과 가상환경만 포함
FROM python:3.12-slim

# 동일하게 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 빌드 스테이지에서 만든 가상환경 복사
COPY --from=builder /venv /venv

# 전체 코드 복사
COPY . .

# 가상환경의 bin 경로를 PATH에 추가해서 기본 python/pip가 가상환경 버전을 사용하도록 함
ENV PATH="/venv/bin:$PATH"

CMD ["python", "realtime_container_process_backbone.py"]
