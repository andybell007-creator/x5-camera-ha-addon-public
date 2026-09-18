FROM python:3.12-slim
RUN mkdir -p /app
COPY ziot_rtp_bridge.py gen_config.py /app/
WORKDIR /app
CMD ["sh", "-c", "python3 /app/gen_config.py && exec python3 /app/ziot_rtp_bridge.py --config /app/ziot_config.json"]
