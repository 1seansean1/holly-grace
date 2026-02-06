"""Fallback chain wrapper: wraps each model with ordered fallbacks."""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel

from src.llm.config import FALLBACK_CHAINS, ModelID
from src.llm.router import LLMRouter

logger = logging.getLogger(__name__)


def get_model_with_fallbacks(
    router: LLMRouter,
    model_id: ModelID,
) -> BaseChatModel:
    """Wrap a model with its fallback chain using LangChain's with_fallbacks().

    If primary model fails, automatically tries the next model in the chain.
    """
    primary = router.get_model(model_id)
    fallback_ids = FALLBACK_CHAINS.get(model_id, [])

    if not fallback_ids:
        return primary

    fallbacks = []
    for fb_id in fallback_ids:
        try:
            fallbacks.append(router.get_model(fb_id))
        except Exception:
            logger.warning("Could not create fallback model %s", fb_id)

    if not fallbacks:
        return primary

    return primary.with_fallbacks(fallbacks)
