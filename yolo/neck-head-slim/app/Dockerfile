# 빌드 스테이지: 의존성 설치 + 가상환경 구성
FROM python:3.12-slim as builder

WORKDIR /app

# 필수 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt만 먼저 복사
COPY requirements.txt .

# pip 업그레이드 + 가상환경 생성 후 의존성 설치
RUN python -m pip install --upgrade pip \
    && python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------

# 실행 스테이지: 빌드 스테이지에서 만들어진 venv만 복사 + 실행에 필요한 코드 복사
FROM python:3.12-slim

WORKDIR /app

# 동일하게 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 빌드 스테이지에서 준비한 가상환경 복사
COPY --from=builder /venv /venv

# 필요한 소스 전체 복사 (불필요한 파일까지 전부 복사하지 않도록 .dockerignore에 설정해두면 좋음)
COPY . .

# venv에 들어있는 파이썬/패키지들을 기본 사용하도록 PATH 설정
ENV PATH="/venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "server_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]
