FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY radar ./radar
COPY web-react/dist ./web-react/dist
COPY radar_ops.json.example ./radar_ops.json.example

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV RADAR_ALLOW_PUBLIC=1

EXPOSE 8000

CMD ["sh", "-c", "python -m radar documents-migrate --db /app/data/radar.sqlite3 && python -m radar serve --db /app/data/radar.sqlite3 --host 0.0.0.0 --port ${PORT:-8000}"]
