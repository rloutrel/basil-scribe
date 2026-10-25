# Basil — Scribe

Basil (Basil — Assistant Synthétique à Intelligence Libre; English:
Synthetic Assistant with Free Intelligence) is a personal platform
combining several standalone components. This repository is the
**writing assistant component**: a generic, multi-profile tool that
drafts replies to recurring correspondence tasks (a resignation, an
application, a quote request…) by reusing the replies **actually sent in
the past**. Every draft requires human review before use — nothing is
ever sent automatically.

It is a standalone Django project, fully self-contained and runnable on
its own. Sibling components: basil-chambellan (authentication and model
access), basil-mail (mail collection and sorting), basil-correspondant
(external correspondence, MCP), basil-chancelier (calendars, contacts),
basil-concierge (orchestration). Today the mail archive comes from an
export mounted into the container; later, basil-mail will be able to
feed this service.

## Concept

**Precedent-based assisted drafting**: for a recurring correspondence
task, basil-scribe generates a reply draft inspired by the replies
really sent in the past, with mandatory human review before any use.

All the specificity of a use case lives in a **profile** (a YAML file)
created and edited **after deployment**: organization identity, working
language, request types, business rules, tone, signature. The code knows
no use case. One instance can host several independent profiles
(a club membership desk, a freelance business, …), strictly isolated
from each other.

Everything runs locally: the LLM (Ollama), the embeddings
(FlagEmbedding bge-m3) and the mail archive (mounted read-only). No data
is ever sent to an external service.

## The four-step flow

1. **Extract precedents** — `python manage.py build_precedents --profile <name>`
   scans `MAIL_EXPORT_ROOT/<mail_source>/` for every `.eml`, identifies
   requests per configured request type (pure heuristics: subject
   keyword, or sender domain + type mention, or an indicative folder
   signal — content first, folder structure never exclusive), pairs
   each request with the reply actually sent (In-Reply-To/References
   first; fallback: same normalized subject within a ±3-day window,
   flagged `heuristic`), embeds the request body and stores one
   `Precedent` per pair. Idempotent: the deduplication key is
   `sha256(request Message-ID + reply date + profile)`, so re-running
   never duplicates; `--rebuild` clears the profile's local cache
   first. A report is printed at the end (mails parsed, requests per
   type and per criterion, pairs matched, requests without reply,
   heuristic matches, unmatched replies, ambiguous mails).
2. **Typology** — `python manage.py classify_precedents --profile <name>`
   asks the LLM (one call per pair, profile language, taxonomy from the
   profile, one few-shot example, strict JSON with a tolerant regex
   fallback) to file each reply into one of the type's
   `answer_categories`. Failures are non-fatal and simply stay
   unclassified for a later re-run.
3. **Draft** — on the home page, choose a request type, paste the
   request text (date and recipient name optional). Generation runs
   **asynchronously**: the POST queues a task and returns immediately,
   and the page polls the status every 2 seconds (spinner + progress
   label: embedding model load, similar-precedent search, LLM call) so
   a first run that downloads and loads bge-m3 never blocks or times
   out. When done, the draft appears in an editable textarea; on
   failure the error is shown with a retry button. The request is
   embedded, the top-3 precedents **of the same profile and the same
   request type** are selected by cosine similarity (numpy over stored
   vectors — no external vector database at this scale), and the
   generation prompt is assembled in the profile language in this
   order: role prompt, business rules, reserved context block (empty in
   v1), current request, the 3 precedents as few-shot examples
   ("Ähnlicher Fall"), form constraints (greeting, signature,
   ready-to-send answer, invent nothing). The precedents used are shown
   collapsed for transparency; "Next version" regenerates while
   excluding a precedent.
4. **Review and log** — the draft stays editable; there is no SMTP in
   v1 and there will never be automatic sending (Basil rule: any reply
   to a third party requires human validation). "Take over" saves the
   final version; the drafts history is filterable by profile and type;
   "Add as precedent" feeds the accepted (request, final reply) pair
   back into the profile's index, so the tool improves with use.

## Installation

### With Docker (recommended)

Requirements: Docker and Docker Compose.

```bash
git clone https://github.com/rloutrel/basil-scribe.git
cd basil-scribe
cp .env.example .env        # edit DJANGO_SECRET_KEY and credentials
mkdir -p mail-exports profiles
docker compose up --build -d
```

Services: `web` (Django + gunicorn, static files served by
WhiteNoise), `ollama` (model volume, model
pulled at first start by the entrypoint), `db` (PostgreSQL, named
volume). The mail archive is mounted read-only
(`./mail-exports:/data/mail-exports:ro`) — the tool can never modify or
delete the originals. The `profiles/` directory is mounted read-write
outside the image, so profiles can be edited after deployment without a
rebuild. The entrypoint runs migrations, `collectstatic`, profile
validation/sync and the Ollama model pull, then starts gunicorn. The
application is available at [http://localhost:8000](http://localhost:8000)
(configurable with `WEB_PORT`).

#### Updating without re-downloading everything

The heavy dependencies (torch, FlagEmbedding, ~2 GB) and the embedding
model are each downloaded **once** and then cached:

- the Dockerfile installs requirements in a dedicated layer with a
  BuildKit pip cache mount — adding a small dependency later downloads
  only that package, and a code-only change does not even touch the
  dependency layer (requires BuildKit, default since Docker 23);
- the bge-m3 embedding model lives in the `hf_cache` named volume —
  it survives rebuilds and restarts.

So the gentle update flow is:

```bash
git pull
COMPOSE_FILE=docker-compose.yml:docker-compose.host-ollama.yml \
  docker compose up -d --build
```

The first `--build` after adding a dependency still re-runs `pip
install`, but from the warm wheel cache — seconds, not a full
re-download. If only Python/HTML/CSS code changed, you can even skip
the rebuild and restart with the new code mounted — not applicable here
since code is baked into the image, so keep `--build`; it is cheap
after the first time. If a build ever goes wrong and you want a truly
clean slate, `docker builder prune` clears the BuildKit cache (next
build downloads everything again).

#### Reusing an Ollama server you already have

If you already run Ollama on the Docker host (or any reachable
machine), skip the bundled `ollama` service entirely with the override
file (Docker Compose v2.24+) — no second image download, no duplicate
model volume:

```bash
docker compose -f docker-compose.yml -f docker-compose.host-ollama.yml up -d
# or persistently:
COMPOSE_FILE=docker-compose.yml:docker-compose.host-ollama.yml docker compose up -d
```

The web service then reaches your server through
`http://host.docker.internal:11434/v1` by default; override with
`OLLAMA_HOST_URL` (keep the `/v1` suffix, the OpenAI SDK expects it).
`LLM_MODEL` must name a model your Ollama already serves.

### Without Docker

Requirements: Python 3.12+, a PostgreSQL server, a local Ollama (or an
OpenAI-compatible endpoint).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # point POSTGRES_*/OLLAMA_BASE_URL at your setup
set -a; source .env; set +a
python manage.py migrate
python manage.py collectstatic
python manage.py runserver
```

### Creating a superuser (admin)

```bash
python manage.py createsuperuser             # non-Docker
docker compose exec web python manage.py createsuperuser  # Docker
```

## Profiles

A profile is one `profiles/<name>.yaml` file. `profiles/example.yaml`
is a fully documented example shipped with the repo. All keys are in
English; the values stay in the working language of the profile.

```yaml
profile:
  name: "Förderkreis Romain-Rolland — Mitgliedschaft"  # displayed in the UI
  language: "de"                  # working language: UI, prompts, labels
  mail_source: "fk-roro"          # subfolder of MAIL_EXPORT_ROOT to scan

organization:
  name: "Förderkreis Romain-Rolland e.V."
  greeting: "Sie"                 # required politeness form
  signature: |                    # appended to every generated reply
    Mit freundlichen Grüßen
    Der Vorstand
  rules: |                        # business rules, injected into the prompt
    Die Mitgliedschaft endet zum Ende des laufenden Kalenderjahres.
    Beiträge werden nicht anteilig erstattet.

role_prompt: |                    # writer's role, injected as-is
  Du bist ein ehrenamtliches Vorstandsmitglied und antwortest auf
  Mitgliedschafts-Anliegen höflich, persönlich und klar.

temperature: 0.5                  # optional generation temperature

request_types:                    # 1..n request types of the profile
  resignation:
    name: "Kündigung der Mitgliedschaft"
    subject_keywords: ["kündigung"]   # subject contains one of these…
    sender_domains: ["fk-roro.de"]    # …or sender in these domains + type mention
    folders: ["Kündigung_*"]          # indicative signal, never exclusive
    answer_categories: ["acknowledge_receipt", "confirm_end", "followup_question", "other"]

context:                          # anticipated extension, disabled in v1
  enabled: false
```

Key documentation:

- `profile.name` — display name in the UI (also used as the profile key).
- `profile.language` — `en`, `fr` or `de`; drives UI texts, prompts and
  labels. No text is hardcoded: the UI uses Django i18n
  (`LANGUAGE_CODE = "en-gb"`, French and German catalogs included).
- `profile.mail_source` — subfolder of `MAIL_EXPORT_ROOT` scanned by
  `build_precedents`; the archive can host several subtrees, one per
  profile.
- `organization.name`, `organization.greeting`, `organization.signature`,
  `organization.rules` — identity, politeness form, signature and
  business rules injected into every generation prompt.
- `role_prompt` — the writer's role, injected as-is at the top.
- `temperature` — optional per-profile generation temperature (default
  from `DEFAULT_LLM_TEMPERATURE`, 0.7).
- `request_types.<key>.name` — display name of the request type.
- `request_types.<key>.subject_keywords` — identification by subject.
- `request_types.<key>.sender_domains` — identification by sender domain
  when the type is also mentioned in subject or body.
- `request_types.<key>.folders` — glob patterns matched against folder
  names; an additional, never exclusive signal (manual archive sorting
  is only indicative).
- `request_types.<key>.answer_categories` — the taxonomy used by
  `classify_precedents`; a request type without categories is invalid.
- `context` — anticipated extension (see below); keep `enabled: false`.

Validate a profile (error messages are rendered in the profile language):

```bash
python manage.py check_config                    # all profiles
python manage.py check_config --profile fk-roro  # one profile
python manage.py check_config --sync             # also sync to the database
```

The UI has a profile selector in the navbar; the active profile is kept
in the session and its language drives the interface. Each profile has
its own precedents and drafts — a precedent of profile A is never
offered to profile B.

### Adding a second profile

1. Create `profiles/<name>.yaml` (copy `profiles/example.yaml`).
2. Put the corresponding mail export under
   `mail-exports/<mail_source>/`.
3. `python manage.py check_config --sync`
4. `python manage.py build_precedents --profile <name>`
5. Select the new profile in the navbar dropdown — its precedents,
   drafts and interface language are fully independent of the first
   profile's.

## Model access seam (basil-chambellan)

In v1 the LLM (local Ollama, reached through the OpenAI SDK) and the
embeddings (FlagEmbedding `BGEM3FlagModel`) are accessed directly, with
no intermediary. All remote access goes exclusively through
`core/llm.py` and `core/embeddings.py`: these two modules are the single
seam with basil-chambellan, the future central broker for model access
(local vs remote, model per task, API tokens). Nothing else in the
codebase may call Ollama or the OpenAI SDK. No chambellan integration is
implemented in v1 — only the separation.

The embedding device is resolved from `EMBED_DEVICE` (default `cpu`;
`use_fp16` is only enabled when the device is not cpu) and is never
hardcoded to `mps` or `cuda`.

## Anticipated extension: context (disabled in v1)

Generation reserves an optional "context" block (external historical
context, e.g. a semantic search index over the archive):

- `ContextSource` interface in `core/kontext.py`, default implementation
  `NullContext` (returns an empty list);
- optional `context` key in the profile YAML (`enabled: false` by
  default);
- the block's place is already present in the prompt template (empty in
  v1);
- if the context is disabled or fails, generation works normally —
  never blocking;
- no external adapter is implemented in v1, only the seam.

## Configuration (12-factor)

Configuration is strictly environment-based; `.env.example` documents
every variable: `DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS`, `DJANGO_DEBUG`, `DATABASE_URL` / `POSTGRES_*`,
`DJANGO_TIME_ZONE`, `PROFILES_DIR`, `MAIL_EXPORT_ROOT`,
`OLLAMA_BASE_URL`, `LLM_MODEL`, `OLLAMA_PULL_MODEL`, `EMBED_DEVICE`,
`EMBED_MODEL`, `DEFAULT_LLM_TEMPERATURE`, `WEB_PORT`, `BASIL_LOG_LEVEL`.
No secret is ever hardcoded. The database is PostgreSQL only
(default in settings and in dev; no SQLite fallback).

## Project structure

```
basil_scribe/   Django project (settings, urls, wsgi; test_settings for the suite)
core/           model-access seams, testable in isolation with mocks
  config.py     profile YAML loading and validation (errors in profile language)
  llm.py        LLM access (OpenAI SDK -> Ollama) + tolerant JSON answer parsing
  embeddings.py embedding access (FlagEmbedding bge-m3, device from EMBED_DEVICE)
  kontext.py    ContextSource seam, NullContext default (v1)
profiles/       profile model, YAML sync, check_config command, selector middleware
precedents/     .eml loader, identification/pairing heuristics, index, build & classify commands
drafts/         generation, drafts history, views
templates/      HTMX + Alpine.js server-rendered templates (no JS build step)
static/         CSS custom properties, dark/light themes
tests/          pytest suite, every external brick mocked
```

The UI follows the Basil house style: two pages (the daily drafting page
and the drafts history), a minimal navbar, dark/light mode toggled in
the navbar (persisted in `localStorage`, defaulting to
`prefers-color-scheme`), both themes complete and readable.

## Testing

Every external dependency (LLM, embeddings) is mocked; no test makes a
network call or downloads a model. The suite covers `.eml` parsing
(fixtures with In-Reply-To, without reference, HTML-only,
ISO-8859-1), identification heuristics (varied test configs), pairing
(including the ±3-day window), top-k cosine similarity, tolerant LLM
output parsing, configuration validation, the commands, the views —
and **profile isolation**: a precedent of profile A is never offered to
profile B.

```bash
pytest                          # uses basil_scribe.test_settings (in-memory DB)
```

## License

MIT (see [LICENSE](LICENSE)). Only permissively licensed dependencies
(MIT, BSD, Apache-2.0, ISC, PSF); the registry lives in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The standard library
is preferred wherever possible.
