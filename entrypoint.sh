#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py compilemessages --noinput || true
python manage.py collectstatic --noinput
python manage.py check_config --sync || true

if [ -n "$OLLAMA_PULL_MODEL" ]; then
  echo "Pulling Ollama model $OLLAMA_PULL_MODEL (first start)…"
  until curl -sf "${OLLAMA_BASE_URL%/v1}/api/tags" >/dev/null 2>&1; do
    echo "Waiting for Ollama…"
    sleep 2
  done
  curl -sf "${OLLAMA_BASE_URL%/v1}/api/pull" -d "{\"model\": \"$OLLAMA_PULL_MODEL\"}" \
    || echo "Warning: could not pull $OLLAMA_PULL_MODEL; pull it manually with: docker compose exec ollama ollama pull $OLLAMA_PULL_MODEL"
fi

exec gunicorn basil_scribe.wsgi:application --bind 0.0.0.0:8000 --workers 2
