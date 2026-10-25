"""
Embedding access seam.

In v1 embeddings come from the local FlagEmbedding BGEM3FlagModel. This
module and `core/llm` are the ONLY seams with basil-chambellan, the
future central broker for model access. The device is resolved from the
EMBED_DEVICE environment variable and never hardcoded.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

EMBED_MAX_CHARS = 4000

_MODEL = None


class EmbeddingError(Exception):
    pass


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError:
            raise EmbeddingError("FlagEmbedding is not installed")
        device = settings.EMBED_DEVICE
        _MODEL = BGEM3FlagModel(
            settings.EMBED_MODEL,
            use_fp16=False if device == "cpu" else True,
            devices=[device],
        )
    return _MODEL


def embed(text):
    """Embed a single string (dict keys irrelevant); return a list."""
    if not text:
        text = " "
    text = text[:EMBED_MAX_CHARS]
    model = _get_model()
    try:
        output = model.encode(
            [text], batch_size=1, max_length=EMBED_MAX_CHARS
        )["dense_vecs"]
    except Exception as exc:
        logger.exception("Embedding call failed")
        raise EmbeddingError(str(exc)) from exc
    return output[0].tolist()
