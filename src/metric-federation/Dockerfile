FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY federation_agent.py .

CMD ["python", "-u", "federation_agent.py"]
