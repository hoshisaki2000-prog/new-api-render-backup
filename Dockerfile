FROM calciumion/new-api:latest

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages --no-cache-dir huggingface_hub || pip3 install --no-cache-dir huggingface_hub

COPY start-render.sh /start-render.sh
COPY backup-loop.py /backup-loop.py
RUN chmod +x /start-render.sh /backup-loop.py

WORKDIR /data
CMD ["/start-render.sh"]
