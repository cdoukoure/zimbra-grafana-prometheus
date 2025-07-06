FROM python:3.10-slim

WORKDIR /app

COPY zimbra10_prometheus_exporter.py .

RUN pip install flask prometheus_client psutil requests urllib3

ENV ZEX_PORT=9093
ENV ZEX_TIMEOUT=10
ENV ZEX_DEBUG_JSON=false

EXPOSE 9093

CMD ["python", "zimbra10_prometheus_exporter.py"]
