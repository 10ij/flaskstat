FROM python:3.11-slim

WORKDIR /app

COPY src/ /app

RUN useradd -m monitor
USER monitor

EXPOSE 8080

RUN pip install flask authlib requests python-dotenv

CMD ["python", "main.py"]
