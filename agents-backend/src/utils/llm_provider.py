"""
Unified LLM Provider Factory

Supports multiple LLM providers:
  - OpenAI (via API key and/or base URL)
  - Azure OpenAI (via Azure endpoint, deployment, version)
  - Groq (via Groq API)
  - Google Gemini (via Google API key or OpenAI-compatible endpoint)
    - AWS Bedrock (via AWS credentials chain, region, optional profile)
  - Any OpenAI-compatible provider (via custom base URL)

Configuration via environment variables:
    - LLM_PROVIDER: 'openai', 'azure', 'groq', 'google', 'bedrock', or 'custom'
  - LLM_MODEL: Model name (e.g., 'gpt-4', 'claude-3-5-sonnet', 'mixtral-8x7b-32768')
  - OPENAI_API_KEY: API key for OpenAI / Groq / Google compatible endpoints
  - OPENAI_BASE_URL: Base URL for OpenAI-compatible endpoints

  For Azure OpenAI:
    - AZURE_ENDPOINT: Your Azure endpoint URL
    - AZURE_CHAT_DEPLOYMENT: Deployment name for chat models
    - AZURE_CHAT_VERSION: API version (e.g., '2024-02-01')

  For Groq:
    - GROQ_API_KEY: Groq API key (same as OPENAI_API_KEY if set)

  For Google Gemini:
    - GOOGLE_API_KEY: Google Gemini API key
    - Or use OpenAI-compatible endpoint if provided

    For AWS Bedrock:
        - AWS_REGION or AWS_DEFAULT_REGION: AWS region (e.g., 'us-east-1')
        - AWS_PROFILE: Optional AWS profile name
        - BEDROCK_MODEL_PROVIDER: Optional explicit provider (e.g., 'anthropic')
        - BEDROCK_INFERENCE_PROFILE_ARN or BEDROCK_INFERENCE_PROFILE_ID: Optional
            Inference profile identifier (required by some models for Converse API)
        - AWS credentials should be available via standard AWS SDK chain
"""

import os
import threading
from typing import Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks.base import BaseCallbackHandler
from dotenv import load_dotenv

load_dotenv()


class _TerminalLogLLMCallback(BaseCallbackHandler):
    """Print finalized LLM responses so they appear in terminal and runtime logs."""

    def _stringify_generation(self, generation: Any) -> str:
        if generation is None:
            return ""

        message = getattr(generation, "message", None)
        if message is not None:
            content = getattr(message, "content", "")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if text is not None:
                            parts.append(str(text))
                    else:
                        parts.append(str(item))
                return "\n".join([p for p in parts if p])
            return str(content)

        text = getattr(generation, "text", None)
        if text is not None:
            return str(text)
        return str(generation)

    def _emit_response(self, response: Any) -> None:
        try:
            generations = getattr(response, "generations", None) or []
            outputs: list[str] = []
            for prompt_generations in generations:
                if not prompt_generations:
                    continue
                rendered = self._stringify_generation(prompt_generations[0]).strip()
                if rendered:
                    outputs.append(rendered)

            if not outputs:
                return

            print("\n[LLM OUTPUT BEGIN]")
            for idx, text in enumerate(outputs, start=1):
                if len(outputs) > 1:
                    print(f"[response {idx}]")
                print(text)
            print("[LLM OUTPUT END]\n")
        except Exception:
            # Callback logging must never break the agent flow.
            pass

    def on_llm_end(self, response, **kwargs) -> None:  # noqa: ANN001
        self._emit_response(response)

    def on_chat_model_end(self, response, **kwargs) -> None:  # noqa: ANN001
        self._emit_response(response)


_LLM_CALLBACK = _TerminalLogLLMCallback()
_LLM_SINGLETONS: dict[tuple[Any, ...], BaseChatModel] = {}
_LLM_SINGLETON_LOCK = threading.Lock()


def _provider_env_signature(provider: str) -> tuple[tuple[str, str], ...]:
    provider = (provider or "").lower()
    env_by_provider = {
        "openai": ["OPENAI_BASE_URL", "OPENAI_API_KEY"],
        "custom": ["OPENAI_BASE_URL", "OPENAI_API_KEY"],
        "azure": [
            "AZURE_ENDPOINT",
            "AZURE_CHAT_DEPLOYMENT",
            "AZURE_CHAT_VERSION",
            "AZURE_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ],
        "groq": ["GROQ_API_KEY", "OPENAI_API_KEY"],
        "google": ["GOOGLE_API_KEY"],
        "bedrock": [
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
            "AWS_PROFILE",
            "BEDROCK_MODEL_PROVIDER",
            "BEDROCK_INFERENCE_PROFILE_ARN",
            "BEDROCK_INFERENCE_PROFILE_ID",
        ],
        "cerebras": ["CEREBRAS_API_KEY"],
    }
    names = env_by_provider.get(provider, [])
    return tuple((name, os.getenv(name, "")) for name in names)


def _singleton_key(provider: str, model: str, temperature: float) -> tuple[Any, ...]:
    return (
        (provider or "").lower(),
        model or "",
        float(temperature),
        _provider_env_signature(provider),
    )


def _identifier_disallows_temperature(identifier: str) -> bool:
    """
    Some newer GPT-5 family deployments reject explicit temperature values
    and only accept provider defaults.
    """
    m = (identifier or "").lower()
    return "gpt-5" in m


def _build_model_kwargs(
    model: str, temperature: float, *extra_identifiers: str
) -> dict:
    kwargs = {"model": model}
    disallow = _identifier_disallows_temperature(model) or any(
        _identifier_disallows_temperature(x) for x in extra_identifiers if x
    )
    if not disallow:
        kwargs["temperature"] = temperature
    kwargs["callbacks"] = [_LLM_CALLBACK]
    return kwargs


def _bedrock_temperature_value(model: str, temperature: float) -> Optional[float]:
    if _identifier_disallows_temperature(model):
        return None
    return temperature


def _infer_bedrock_model_provider(model_name: str) -> Optional[str]:
    """Infer Bedrock model provider from common model ID / ARN patterns."""
    if not model_name:
        return None

    lowered = model_name.lower()
    known_providers = ["anthropic", "amazon", "meta", "mistral", "cohere", "ai21"]
    for provider in known_providers:
        if lowered.startswith(f"{provider}."):
            return provider
        if f".{provider}." in lowered:
            return provider
        if f"/{provider}." in lowered:
            return provider
    return None


def get_llm(
    temperature: float = 0,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseChatModel:
    """
    Factory function to get a configured LLM instance.

    Args:
        temperature: Model temperature (0-1)
        provider: LLM provider ('openai', 'azure', 'groq', 'google', 'custom', or None for auto-detect)
        model: Model name (overrides env var)

    Returns:
        A configured BaseChatModel instance

    Raises:
        ValueError: If provider is unsupported or required credentials are missing
    """
    # Determine provider and model from args or env vars
    llm_provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
    llm_model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    print(
        f"LLM Provider: {llm_provider}, Model: {llm_model}, Temperature: {temperature}"
    )

    cache_key = _singleton_key(llm_provider, llm_model, temperature)
    with _LLM_SINGLETON_LOCK:
        cached = _LLM_SINGLETONS.get(cache_key)
        if cached is not None:
            return cached

    if llm_provider == "azure":
        llm = _get_azure_openai(llm_model, temperature)
    elif llm_provider == "groq":
        llm = _get_groq(llm_model, temperature)
    elif llm_provider == "google":
        llm = _get_google_gemini(llm_model, temperature)
    elif llm_provider == "bedrock":
        llm = _get_bedrock(llm_model, temperature)
    elif llm_provider == "cerebras":
        llm = _get_cerebras(llm_model, temperature)
    elif llm_provider == "custom" or llm_provider == "openai":
        # Try OpenAI-compatible endpoint first, then fallback to direct OpenAI
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            llm = _get_openai_compatible(llm_model, base_url, temperature)
        else:
            llm = _get_openai(llm_model, temperature)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {llm_provider}. "
            f"Supported: 'openai', 'azure', 'groq', 'google', 'bedrock', 'cerebras', 'custom'"
        )

    with _LLM_SINGLETON_LOCK:
        _LLM_SINGLETONS[cache_key] = llm
    return llm


def _get_openai(model: str, temperature: float) -> BaseChatModel:
    """Get OpenAI ChatGPT instance."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required for OpenAI provider"
        )

    return ChatOpenAI(
        **_build_model_kwargs(model, temperature),
        openai_api_key=api_key,
    )


def _get_openai_compatible(
    model: str, base_url: str, temperature: float
) -> BaseChatModel:
    """Get OpenAI-compatible LLM instance (e.g., local server, custom API)."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required for OpenAI-compatible provider"
        )

    return ChatOpenAI(
        **_build_model_kwargs(model, temperature),
        base_url=base_url,
        api_key=api_key,
    )


def _get_azure_openai(model: str, temperature: float) -> BaseChatModel:
    """Get Azure OpenAI instance."""
    from langchain_openai import AzureChatOpenAI

    azure_endpoint = os.getenv("AZURE_ENDPOINT")
    azure_deployment = os.getenv("AZURE_CHAT_DEPLOYMENT")
    azure_api_version = os.getenv("AZURE_CHAT_VERSION", "2024-02-01")
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not azure_endpoint:
        raise ValueError(
            "AZURE_ENDPOINT environment variable is required for Azure OpenAI"
        )
    if not azure_deployment:
        raise ValueError(
            "AZURE_CHAT_DEPLOYMENT environment variable is required for Azure OpenAI"
        )
    if not api_key:
        raise ValueError(
            "AZURE_OPENAI_API_KEY or OPENAI_API_KEY environment variable is required for Azure OpenAI"
        )

    model_kwargs = _build_model_kwargs(model, temperature, azure_deployment)
    model_kwargs.pop("model", None)

    return AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
        openai_api_version=azure_api_version,
        api_key=api_key,
        **model_kwargs,
    )


def _get_groq(model: str, temperature: float) -> BaseChatModel:
    """Get Groq LLM instance."""
    try:
        from langchain_groq import ChatGroq
    except ImportError:
        raise ImportError(
            "langchain-groq is required for Groq provider. Install with: pip install langchain-groq"
        )

    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY or OPENAI_API_KEY environment variable is required for Groq provider"
        )

    return ChatGroq(
        **_build_model_kwargs(model, temperature),
        groq_api_key=api_key,
    )


def _get_google_gemini(model: str, temperature: float) -> BaseChatModel:
    """Get Google Gemini instance."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        raise ImportError(
            "langchain-google-genai is required for Google Gemini provider. "
            "Install with: pip install langchain-google-genai"
        )

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY environment variable is required for Google Gemini provider"
        )

    return ChatGoogleGenerativeAI(
        **_build_model_kwargs(model, temperature),
        google_api_key=api_key,
    )


def _get_bedrock(model: str, temperature: float) -> BaseChatModel:
    """Get AWS Bedrock instance using langchain-aws."""
    try:
        from langchain_aws import ChatBedrockConverse
    except ImportError:
        ChatBedrockConverse = None

    try:
        from langchain_aws import ChatBedrock
    except ImportError:
        ChatBedrock = None

    if not ChatBedrockConverse and not ChatBedrock:
        raise ImportError(
            "langchain-aws is required for Bedrock provider. "
            "Install with: pip install langchain-aws"
        )

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise ValueError(
            "AWS_REGION or AWS_DEFAULT_REGION environment variable is required for Bedrock provider"
        )

    profile = os.getenv("AWS_PROFILE")
    explicit_provider = os.getenv("BEDROCK_MODEL_PROVIDER")
    inference_profile = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN") or os.getenv(
        "BEDROCK_INFERENCE_PROFILE_ID"
    )
    effective_model = inference_profile or model
    model_provider = explicit_provider or _infer_bedrock_model_provider(model)
    temp_value = _bedrock_temperature_value(model, temperature)

    base_kwargs = {"region_name": region, "callbacks": [_LLM_CALLBACK]}
    if profile:
        base_kwargs["credentials_profile_name"] = profile

    constructors = [
        (ChatBedrockConverse, "ChatBedrockConverse"),
        (ChatBedrock, "ChatBedrock"),
    ]
    errors = []

    # Some langchain-aws versions expose pydantic-style constructors where signature
    # inspection is not reliable; use runtime fallbacks for known parameter variants.
    for bedrock_cls, cls_name in constructors:
        if not bedrock_cls:
            continue

        attempts = []
        if temp_value is not None:
            attempts.extend(
                [
                    {
                        **base_kwargs,
                        "model": effective_model,
                        "temperature": temp_value,
                    },
                    {
                        **base_kwargs,
                        "model_id": effective_model,
                        "temperature": temp_value,
                    },
                    {
                        **base_kwargs,
                        "model": effective_model,
                        "model_kwargs": {"temperature": temp_value},
                    },
                    {
                        **base_kwargs,
                        "model_id": effective_model,
                        "model_kwargs": {"temperature": temp_value},
                    },
                ]
            )
        else:
            attempts.extend(
                [
                    {**base_kwargs, "model": effective_model},
                    {**base_kwargs, "model_id": effective_model},
                    {**base_kwargs, "model": effective_model, "model_kwargs": {}},
                    {**base_kwargs, "model_id": effective_model, "model_kwargs": {}},
                ]
            )

        if model_provider:
            if temp_value is not None:
                attempts.extend(
                    [
                        {
                            **base_kwargs,
                            "model": effective_model,
                            "temperature": temp_value,
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model_id": effective_model,
                            "temperature": temp_value,
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model": effective_model,
                            "model_kwargs": {"temperature": temp_value},
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model_id": effective_model,
                            "model_kwargs": {"temperature": temp_value},
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model": effective_model,
                            "temperature": temp_value,
                            "provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model_id": effective_model,
                            "temperature": temp_value,
                            "provider": model_provider,
                        },
                    ]
                )
            else:
                attempts.extend(
                    [
                        {
                            **base_kwargs,
                            "model": effective_model,
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model_id": effective_model,
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model": effective_model,
                            "model_kwargs": {},
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model_id": effective_model,
                            "model_kwargs": {},
                            "model_provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model": effective_model,
                            "provider": model_provider,
                        },
                        {
                            **base_kwargs,
                            "model_id": effective_model,
                            "provider": model_provider,
                        },
                    ]
                )

        for attempt_kwargs in attempts:
            try:
                return bedrock_cls(**attempt_kwargs)
            except Exception as exc:
                errors.append(f"{cls_name}({', '.join(attempt_kwargs.keys())}): {exc}")

    error_preview = " | ".join(errors[:3])
    raise ValueError(
        "Unable to initialize AWS Bedrock provider with current langchain-aws version. "
        "If you see 'on-demand throughput is not supported', set "
        "BEDROCK_INFERENCE_PROFILE_ARN (or BEDROCK_INFERENCE_PROFILE_ID) and keep "
        "LLM_MODEL as your base model. If you see model ARN/provider errors, set "
        "BEDROCK_MODEL_PROVIDER (e.g., anthropic). "
        f"Tried multiple constructor variants. First errors: {error_preview}"
    )


def _get_cerebras(model: str, temperature: float) -> BaseChatModel:
    """Get Cerebras instance using langchain_cerebras ChatCerebras."""
    try:
        from langchain_cerebras import ChatCerebras
    except ImportError:
        raise ImportError(
            "langchain_cerebras is required for Cerebras provider. "
            "Install with: pip install langchain_cerebras"
        )

    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError(
            "CEREBRAS_API_KEY environment variable is required for Cerebras provider"
        )

    return ChatCerebras(
        **_build_model_kwargs(model, temperature),
        max_tokens=1024,
        api_key=api_key,
    )
