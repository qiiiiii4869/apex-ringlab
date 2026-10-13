FROM python:3.13.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /app
ARG DEBIAN_MIRROR
ARG PYPI_INDEX_URL=https://pypi.org/simple
RUN if [ -n "$DEBIAN_MIRROR" ]; then \
      sed -i "s|http://deb.debian.org|$DEBIAN_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 ringlab
COPY requirements.lock.txt ./
ARG PIP_NO_INDEX
ARG PIP_FIND_LINKS
RUN pip install --no-cache-dir --index-url "$PYPI_INDEX_URL" -r requirements.lock.txt
COPY ringlab ./ringlab
COPY web ./web
COPY models ./models
COPY data/rings.json ./data/rings.json
COPY data/training/manifest.json data/training/example-query.json ./data/training/
USER ringlab
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('RINGLAB_PORT','8765')+'/api/health',timeout=3)"
CMD ["python", "-m", "ringlab.server"]
