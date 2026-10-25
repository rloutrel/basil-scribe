# Third-party notices

Basil — scribe (reply drafting from precedents) is MIT-licensed. It
depends on the following permissively licensed third-party packages:

| Package | License | Notes |
|---|---|---|
| Django | BSD-3-Clause | Web framework, ORM, admin |
| psycopg (binary) | Apache-2.0 | PostgreSQL adapter, Django 5 native support |
| dj-database-url | MIT | DATABASE_URL parsing |
| python-dotenv | BSD-3-Clause | .env loading |
| PyYAML | MIT | Profile YAML parsing |
| numpy | BSD-3-Clause | Cosine similarity over stored embeddings |
| openai (SDK) | Apache-2.0 | Client SDK pointed at the local Ollama server |
| FlagEmbedding | MIT | BGEM3FlagModel embeddings (bge-m3), local |
| gunicorn | MIT | WSGI HTTP server |
| whitenoise | MIT | Serves collected static files from gunicorn |
| pytest | MIT | Test runner (development only) |
| pytest-django | BSD-3-Clause | Django integration for pytest (development only) |

Runtime services (never distributed with this repository):

| Service | License | Notes |
|---|---|---|
| Ollama | MIT | Local LLM server, model pulled at first start |
| PostgreSQL | PostgreSQL License | Database, permissive, not copied or distributed |
| bge-m3 model (BAAI) | MIT | Downloaded at first start into the local HF cache |

Frontend assets loaded at runtime (not distributed with this repository):

| Asset | License |
|---|---|
| HTMX | BSD-2-Clause |
| Alpine.js | MIT |

Everything else is the Python standard library (`email`, `hashlib`,
`json`, `re`, `fnmatch`, `pathlib`, `datetime`).
