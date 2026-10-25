FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_CACHE_DIR=/cache/pip

WORKDIR /app

# Copy and install the dependencies in a dedicated layer, with BuildKit's
# pip cache mount: the downloaded wheels persist ACROSS builds, so adding
# a small dependency later (e.g. whitenoise) only downloads that package,
# and torch / FlagEmbedding are never re-fetched. A code-only change does
# not touch this layer at all.
# Requires DOCKER_BUILDKIT=1 (default since Docker 23).
COPY requirements.txt .
RUN --mount=type=cache,target=/cache/pip \
    apt-get update && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput \
    && adduser --disabled-password --no-create-home basil \
    && mkdir -p /app/profiles /data/mail-exports \
    && chown -R basil:basil /app

USER basil

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
