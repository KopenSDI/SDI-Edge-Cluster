FROM python:3.12-slim

WORKDIR /app

# 의존성 파일 복사
COPY requirements.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY scheduler.py .

# 실행 권한 부여
RUN chmod +x scheduler.py

# 실행
CMD ["python3", "scheduler.py"]


