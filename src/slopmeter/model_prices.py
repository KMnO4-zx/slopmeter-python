from __future__ import annotations

# Prices are per 1M tokens in their source currency. The pricing layer converts
# them to USD using EXCHANGE_RATES, so RMB/CNY source prices can stay as CNY.

PRICE_CATALOG_LAST_UPDATED = "2026-06-02"

# Update this when refreshing CNY-denominated prices.
USD_PER_CNY = 0.147
EXCHANGE_RATES = {
    "CNY": {
        "usd_per_unit": USD_PER_CNY,
        "as_of": "2026-06-02",
        "source": "https://cny.currencyrate.today/usd",
        "note": "Editable CNY to USD rate used for CNY-denominated model prices.",
    },
}


def convert_price_to_usd(value: float, source_currency: str = "USD") -> float:
    if source_currency == "USD":
        return float(value)
    rate = EXCHANGE_RATES[source_currency]["usd_per_unit"]
    return round(float(value) * float(rate), 6)


OPENAI_MODEL_PRICES: dict[str, dict[str, object]] = {
    # OpenAI API standard pricing, short-context where tiers exist.
    "gpt-5.5": {
        "display_name": "gpt-5.5",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 5.00,
        "cached_input_per_million": 0.50,
        "cache_write_per_million": 5.00,
        "output_per_million": 30.00,
        "source": "https://developers.openai.com/api/docs/pricing",
    },
    "gpt-5.5-pro": {
        "display_name": "gpt-5.5-pro",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 30.00,
        "cached_input_per_million": 30.00,
        "cache_write_per_million": 30.00,
        "output_per_million": 180.00,
        "source": "https://developers.openai.com/api/docs/pricing",
        "note": "OpenAI lists no cached-input discount for pro.",
    },
    "gpt-5.4": {
        "display_name": "gpt-5.4",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 2.50,
        "cached_input_per_million": 0.25,
        "cache_write_per_million": 2.50,
        "output_per_million": 15.00,
        "source": "https://developers.openai.com/api/docs/pricing",
    },
    "gpt-5.4-mini": {
        "display_name": "gpt-5.4-mini",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 0.75,
        "cached_input_per_million": 0.075,
        "cache_write_per_million": 0.75,
        "output_per_million": 4.50,
        "source": "https://developers.openai.com/api/docs/pricing",
    },
    "gpt-5.4-nano": {
        "display_name": "gpt-5.4-nano",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 0.20,
        "cached_input_per_million": 0.02,
        "cache_write_per_million": 0.20,
        "output_per_million": 1.25,
        "source": "https://developers.openai.com/api/docs/pricing",
    },
    "gpt-5.4-pro": {
        "display_name": "gpt-5.4-pro",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 30.00,
        "cached_input_per_million": 30.00,
        "cache_write_per_million": 30.00,
        "output_per_million": 180.00,
        "source": "https://developers.openai.com/api/docs/pricing",
        "note": "OpenAI lists no cached-input discount for pro.",
    },
    "gpt-5.3-codex": {
        "display_name": "gpt-5.3-codex",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 1.75,
        "cached_input_per_million": 0.175,
        "cache_write_per_million": 1.75,
        "output_per_million": 14.00,
        "source": "https://developers.openai.com/api/docs/pricing",
    },
    "chat-latest": {
        "display_name": "chat-latest",
        "provider": "openai",
        "source_currency": "USD",
        "input_per_million": 5.00,
        "cached_input_per_million": 0.50,
        "cache_write_per_million": 5.00,
        "output_per_million": 30.00,
        "source": "https://developers.openai.com/api/docs/pricing",
    },
}


ANTHROPIC_MODEL_PRICES: dict[str, dict[str, object]] = {
    # Anthropic Claude first-party API standard global pricing. Cache write is
    # the 5-minute cache write rate; 1-hour writes cost 2x base input.
    "claude-opus-4-8": {
        "display_name": "claude-opus-4-8",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 5.00,
        "cached_input_per_million": 0.50,
        "cache_write_per_million": 6.25,
        "output_per_million": 25.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-opus-4-7": {
        "display_name": "claude-opus-4-7",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 5.00,
        "cached_input_per_million": 0.50,
        "cache_write_per_million": 6.25,
        "output_per_million": 25.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-opus-4-6": {
        "display_name": "claude-opus-4-6",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 5.00,
        "cached_input_per_million": 0.50,
        "cache_write_per_million": 6.25,
        "output_per_million": 25.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-opus-4-5": {
        "display_name": "claude-opus-4-5",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 5.00,
        "cached_input_per_million": 0.50,
        "cache_write_per_million": 6.25,
        "output_per_million": 25.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-opus-4-1": {
        "display_name": "claude-opus-4-1",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 15.00,
        "cached_input_per_million": 1.50,
        "cache_write_per_million": 18.75,
        "output_per_million": 75.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-sonnet-4-6": {
        "display_name": "claude-sonnet-4-6",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 3.00,
        "cached_input_per_million": 0.30,
        "cache_write_per_million": 3.75,
        "output_per_million": 15.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-sonnet-4-5": {
        "display_name": "claude-sonnet-4-5",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 3.00,
        "cached_input_per_million": 0.30,
        "cache_write_per_million": 3.75,
        "output_per_million": 15.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-sonnet-4": {
        "display_name": "claude-sonnet-4",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 3.00,
        "cached_input_per_million": 0.30,
        "cache_write_per_million": 3.75,
        "output_per_million": 15.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-haiku-4-5": {
        "display_name": "claude-haiku-4-5",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 1.00,
        "cached_input_per_million": 0.10,
        "cache_write_per_million": 1.25,
        "output_per_million": 5.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
    "claude-3-5-haiku": {
        "display_name": "claude-3-5-haiku",
        "provider": "anthropic",
        "source_currency": "USD",
        "input_per_million": 0.80,
        "cached_input_per_million": 0.08,
        "cache_write_per_million": 1.00,
        "output_per_million": 4.00,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    },
}


DEEPSEEK_MODEL_PRICES: dict[str, dict[str, object]] = {
    # DeepSeek API. The legacy deepseek-chat and deepseek-reasoner names map to
    # deepseek-v4-flash compatibility modes on the official pricing page.
    "deepseek-v4-flash": {
        "display_name": "deepseek-v4-flash",
        "provider": "deepseek",
        "source_currency": "CNY",
        "input_per_million": 1.00,
        "cached_input_per_million": 0.02,
        "cache_write_per_million": 1.00,
        "output_per_million": 2.00,
        "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
    },
    "deepseek-v4-pro": {
        "display_name": "deepseek-v4-pro",
        "provider": "deepseek",
        "source_currency": "CNY",
        "input_per_million": 3.00,
        "cached_input_per_million": 0.025,
        "cache_write_per_million": 3.00,
        "output_per_million": 6.00,
        "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
    },
    "deepseek-chat": {
        "display_name": "deepseek-chat",
        "provider": "deepseek",
        "source_currency": "CNY",
        "input_per_million": 1.00,
        "cached_input_per_million": 0.02,
        "cache_write_per_million": 1.00,
        "output_per_million": 2.00,
        "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        "note": "Compatibility name for deepseek-v4-flash non-thinking mode.",
    },
    "deepseek-reasoner": {
        "display_name": "deepseek-reasoner",
        "provider": "deepseek",
        "source_currency": "CNY",
        "input_per_million": 1.00,
        "cached_input_per_million": 0.02,
        "cache_write_per_million": 1.00,
        "output_per_million": 2.00,
        "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        "note": "Compatibility name for deepseek-v4-flash thinking mode.",
    },
}


MINIMAX_MODEL_PRICES: dict[str, dict[str, object]] = {
    # MiniMax API pay-as-you-go. M3 standard uses the full China mainland
    # price for <=512k input tokens, ignoring limited-time discounts.
    "minimax-m3": {
        "display_name": "MiniMax-M3",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 4.20,
        "cached_input_per_million": 0.84,
        "cache_write_per_million": 4.20,
        "output_per_million": 16.80,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
    "minimax-m3-long": {
        "display_name": "MiniMax-M3 >512k",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 8.40,
        "cached_input_per_million": 1.68,
        "cache_write_per_million": 8.40,
        "output_per_million": 33.60,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
    "minimax-m2.7": {
        "display_name": "MiniMax-M2.7",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 2.10,
        "cached_input_per_million": 0.42,
        "cache_write_per_million": 2.625,
        "output_per_million": 8.40,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
    "minimax-m2.7-highspeed": {
        "display_name": "MiniMax-M2.7-highspeed",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 4.20,
        "cached_input_per_million": 0.42,
        "cache_write_per_million": 2.625,
        "output_per_million": 16.80,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
    "minimax-m2.5": {
        "display_name": "MiniMax-M2.5",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 2.10,
        "cached_input_per_million": 0.21,
        "cache_write_per_million": 2.625,
        "output_per_million": 8.40,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
    "minimax-m2.5-highspeed": {
        "display_name": "MiniMax-M2.5-highspeed",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 4.20,
        "cached_input_per_million": 0.21,
        "cache_write_per_million": 2.625,
        "output_per_million": 16.80,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
    "minimax-m2.1": {
        "display_name": "MiniMax-M2.1",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 2.10,
        "cached_input_per_million": 0.21,
        "cache_write_per_million": 2.625,
        "output_per_million": 8.40,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
    "minimax-m2": {
        "display_name": "MiniMax-M2",
        "provider": "minimax",
        "source_currency": "CNY",
        "input_per_million": 2.10,
        "cached_input_per_million": 0.21,
        "cache_write_per_million": 2.625,
        "output_per_million": 8.40,
        "source": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
    },
}


MIMO_MODEL_PRICES: dict[str, dict[str, object]] = {
    # Xiaomi MiMo domestic prices are stored as CNY and converted at runtime.
    "mimo-v2.5-pro": {
        "display_name": "mimo-v2.5-pro",
        "provider": "xiaomi-mimo",
        "source_currency": "CNY",
        "input_per_million": 3.00,
        "cached_input_per_million": 0.025,
        "cache_write_per_million": 0.0,
        "output_per_million": 6.00,
        "source": "https://platform.xiaomimimo.com/docs/zh-CN/price/pay-as-you-go",
        "note": "Domestic pricing; cache write is listed as limited-time free.",
    },
    "mimo-v2.5": {
        "display_name": "mimo-v2.5",
        "provider": "xiaomi-mimo",
        "source_currency": "CNY",
        "input_per_million": 1.00,
        "cached_input_per_million": 0.02,
        "cache_write_per_million": 0.0,
        "output_per_million": 2.00,
        "source": "https://platform.xiaomimimo.com/docs/zh-CN/price/pay-as-you-go",
        "note": "Domestic pricing; cache write is listed as limited-time free.",
    },
    "mimo-v2-pro": {
        "display_name": "mimo-v2-pro",
        "provider": "xiaomi-mimo",
        "source_currency": "CNY",
        "input_per_million": 3.00,
        "cached_input_per_million": 0.025,
        "cache_write_per_million": 0.0,
        "output_per_million": 6.00,
        "source": "https://platform.xiaomimimo.com/docs/zh-CN/price/pay-as-you-go",
        "note": "Domestic pricing; auto-routed to V2.5 pricing; cache write is listed as limited-time free.",
    },
    "mimo-v2-omni": {
        "display_name": "mimo-v2-omni",
        "provider": "xiaomi-mimo",
        "source_currency": "CNY",
        "input_per_million": 1.00,
        "cached_input_per_million": 0.02,
        "cache_write_per_million": 0.0,
        "output_per_million": 2.00,
        "source": "https://platform.xiaomimimo.com/docs/zh-CN/price/pay-as-you-go",
        "note": "Domestic pricing; auto-routed to V2.5 pricing; cache write is listed as limited-time free.",
    },
    "off-v2-flash": {
        "display_name": "off-v2-flash",
        "provider": "xiaomi-mimo",
        "source_currency": "CNY",
        "input_per_million": 0.70,
        "cached_input_per_million": 0.07,
        "cache_write_per_million": 0.0,
        "output_per_million": 2.10,
        "source": "https://platform.xiaomimimo.com/docs/zh-CN/price/pay-as-you-go",
        "note": "Domestic pricing; cache write is listed as limited-time free.",
    },
}


GLM_MODEL_PRICES: dict[str, dict[str, object]] = {
    # BigModel / GLM domestic CNY text-model prices. Tiered models use the
    # shortest input tier by default.
    "glm-5.1": {
        "display_name": "GLM-5.1",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 6.00,
        "cached_input_per_million": 1.30,
        "cache_write_per_million": 6.00,
        "output_per_million": 24.00,
        "source": "https://bigmodel.cn/pricing",
        "note": "Input length [0,32K) tier.",
    },
    "glm-5": {
        "display_name": "GLM-5",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 4.00,
        "cached_input_per_million": 1.00,
        "cache_write_per_million": 4.00,
        "output_per_million": 18.00,
        "source": "https://bigmodel.cn/pricing",
        "note": "Input length [0,32K) tier.",
    },
    "glm-5-turbo": {
        "display_name": "GLM-5-Turbo",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 5.00,
        "cached_input_per_million": 1.20,
        "cache_write_per_million": 5.00,
        "output_per_million": 22.00,
        "source": "https://bigmodel.cn/pricing",
        "note": "Input length [0,32K) tier.",
    },
    "glm-4.7": {
        "display_name": "GLM-4.7",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 2.00,
        "cached_input_per_million": 0.40,
        "cache_write_per_million": 2.00,
        "output_per_million": 8.00,
        "source": "https://bigmodel.cn/pricing",
        "note": "Input length [0,32K) and output length [0,0.2K) tier.",
    },
    "glm-4.7-flashx": {
        "display_name": "GLM-4.7-FlashX",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 0.50,
        "cached_input_per_million": 0.10,
        "cache_write_per_million": 0.50,
        "output_per_million": 3.00,
        "source": "https://bigmodel.cn/pricing",
    },
    "glm-4.6": {
        "display_name": "GLM-4.6",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 2.00,
        "cached_input_per_million": 0.40,
        "cache_write_per_million": 2.00,
        "output_per_million": 8.00,
        "source": "https://bigmodel.cn/pricing",
        "note": "Legacy model retained with the GLM-4.7 short-tier domestic price.",
    },
    "glm-4.5": {
        "display_name": "GLM-4.5",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 0.80,
        "cached_input_per_million": 0.16,
        "cache_write_per_million": 0.80,
        "output_per_million": 2.00,
        "source": "https://docs.bigmodel.cn/cn/guide/models/text/glm-4.5",
    },
    "glm-4.5-air": {
        "display_name": "GLM-4.5-Air",
        "provider": "zai-glm",
        "source_currency": "CNY",
        "input_per_million": 0.80,
        "cached_input_per_million": 0.16,
        "cache_write_per_million": 0.80,
        "output_per_million": 2.00,
        "source": "https://bigmodel.cn/pricing",
        "note": "Input length [0,32K) and output length [0,0.2K) tier.",
    },
}


STEPFUN_MODEL_PRICES: dict[str, dict[str, object]] = {
    # StepFun domestic CNY API prices.
    "step-3.7-flash": {
        "display_name": "step-3.7-flash",
        "provider": "stepfun",
        "source_currency": "CNY",
        "input_per_million": 1.35,
        "cached_input_per_million": 0.27,
        "cache_write_per_million": 1.35,
        "output_per_million": 8.10,
        "source": "https://platform.stepfun.com/docs/zh/guides/pricing/details",
    },
    "step-3.5-flash": {
        "display_name": "step-3.5-flash",
        "provider": "stepfun",
        "source_currency": "CNY",
        "input_per_million": 0.70,
        "cached_input_per_million": 0.14,
        "cache_write_per_million": 0.70,
        "output_per_million": 2.10,
        "source": "https://platform.stepfun.com/docs/zh/guides/pricing/details",
    },
    "step-3.5-flash-2603": {
        "display_name": "step-3.5-flash-2603",
        "provider": "stepfun",
        "source_currency": "CNY",
        "input_per_million": 0.70,
        "cached_input_per_million": 0.14,
        "cache_write_per_million": 0.70,
        "output_per_million": 2.10,
        "source": "https://platform.stepfun.com/docs/zh/guides/pricing/details",
        "note": "Compatibility version priced as step-3.5-flash.",
    },
}


GEMINI_MODEL_PRICES: dict[str, dict[str, object]] = {
    # Google Gemini Developer API standard text/image/video token rates.
    "gemini-3.5-flash": {
        "display_name": "gemini-3.5-flash",
        "provider": "google-gemini",
        "source_currency": "USD",
        "input_per_million": 1.50,
        "cached_input_per_million": 0.15,
        "cache_write_per_million": 1.50,
        "output_per_million": 9.00,
        "source": "https://ai.google.dev/gemini-api/docs/pricing",
    },
    "gemini-3.1-flash-lite": {
        "display_name": "gemini-3.1-flash-lite",
        "provider": "google-gemini",
        "source_currency": "USD",
        "input_per_million": 0.25,
        "cached_input_per_million": 0.025,
        "cache_write_per_million": 0.25,
        "output_per_million": 1.50,
        "source": "https://ai.google.dev/gemini-api/docs/pricing",
    },
    "gemini-3.1-pro-preview": {
        "display_name": "gemini-3.1-pro-preview",
        "provider": "google-gemini",
        "source_currency": "USD",
        "input_per_million": 2.00,
        "cached_input_per_million": 0.20,
        "cache_write_per_million": 2.00,
        "output_per_million": 12.00,
        "source": "https://ai.google.dev/gemini-api/docs/pricing",
        "note": "Short-context rate for prompts <=200k tokens.",
    },
    "gemini-3-flash-preview": {
        "display_name": "gemini-3-flash-preview",
        "provider": "google-gemini",
        "source_currency": "USD",
        "input_per_million": 0.50,
        "cached_input_per_million": 0.05,
        "cache_write_per_million": 0.50,
        "output_per_million": 3.00,
        "source": "https://ai.google.dev/gemini-api/docs/pricing",
    },
}


QWEN_MODEL_PRICES: dict[str, dict[str, object]] = {
    # Alibaba Cloud Model Studio / Qwen. Default entries use China mainland CNY
    # short-context prices where tiers exist.
    "qwen3.7-max": {
        "display_name": "qwen3.7-max",
        "provider": "qwen",
        "source_currency": "CNY",
        "input_per_million": 12.00,
        "cached_input_per_million": 12.00,
        "cache_write_per_million": 12.00,
        "output_per_million": 36.00,
        "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        "note": "China mainland deployment, 0<Token<=1M tier.",
    },
    "qwen3-max": {
        "display_name": "qwen3-max",
        "provider": "qwen",
        "source_currency": "CNY",
        "input_per_million": 2.50,
        "cached_input_per_million": 2.50,
        "cache_write_per_million": 2.50,
        "output_per_million": 10.00,
        "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        "note": "China mainland deployment, 0<Token<=32K tier.",
    },
    "qwen-max": {
        "display_name": "qwen-max",
        "provider": "qwen",
        "source_currency": "CNY",
        "input_per_million": 11.743,
        "cached_input_per_million": 11.743,
        "cache_write_per_million": 11.743,
        "output_per_million": 46.971,
        "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        "note": "China mainland deployment, no tiered pricing.",
    },
    "qwen3.6-plus": {
        "display_name": "qwen3.6-plus",
        "provider": "qwen",
        "source_currency": "CNY",
        "input_per_million": 2.00,
        "cached_input_per_million": 2.00,
        "cache_write_per_million": 2.00,
        "output_per_million": 12.00,
        "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        "note": "China mainland deployment, 0<Token<=256K tier.",
    },
    "qwen3.5-plus": {
        "display_name": "qwen3.5-plus",
        "provider": "qwen",
        "source_currency": "CNY",
        "input_per_million": 0.80,
        "cached_input_per_million": 0.80,
        "cache_write_per_million": 0.80,
        "output_per_million": 4.80,
        "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        "note": "China mainland deployment, 0<Token<=128K tier.",
    },
    "qwen-plus": {
        "display_name": "qwen-plus",
        "provider": "qwen",
        "source_currency": "CNY",
        "input_per_million": 0.80,
        "cached_input_per_million": 0.80,
        "cache_write_per_million": 0.80,
        "output_per_million": 2.00,
        "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        "note": "China mainland deployment, 0<Token<=128K tier; thinking output tier is higher.",
    },
    "qwen-turbo": {
        "display_name": "qwen-turbo",
        "provider": "qwen",
        "source_currency": "CNY",
        "input_per_million": 0.30,
        "cached_input_per_million": 0.30,
        "cache_write_per_million": 0.30,
        "output_per_million": 0.60,
        "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        "note": "China mainland deployment; thinking output tier is higher.",
    },
}


KIMI_MODEL_PRICES: dict[str, dict[str, object]] = {
    # Moonshot / Kimi domestic CNY platform prices.
    "kimi-k2.6": {
        "display_name": "kimi-k2.6",
        "provider": "moonshot-kimi",
        "source_currency": "CNY",
        "input_per_million": 6.50,
        "cached_input_per_million": 1.10,
        "cache_write_per_million": 6.50,
        "output_per_million": 27.00,
        "source": "https://platform.kimi.com/docs/pricing/chat-k26",
    },
    "kimi-k2.5": {
        "display_name": "kimi-k2.5",
        "provider": "moonshot-kimi",
        "source_currency": "CNY",
        "input_per_million": 4.00,
        "cached_input_per_million": 0.70,
        "cache_write_per_million": 4.00,
        "output_per_million": 21.00,
        "source": "https://platform.kimi.com/docs/pricing/chat-k25",
    },
    "moonshot-v1": {
        "display_name": "moonshot-v1",
        "provider": "moonshot-kimi",
        "source_currency": "CNY",
        "input_per_million": 10.00,
        "cached_input_per_million": 10.00,
        "cache_write_per_million": 10.00,
        "output_per_million": 30.00,
        "source": "https://platform.kimi.com/docs/pricing/chat-v1",
    },
}


PROVIDER_MODEL_PRICE_TABLES: dict[str, dict[str, dict[str, object]]] = {
    "openai": OPENAI_MODEL_PRICES,
    "anthropic": ANTHROPIC_MODEL_PRICES,
    "deepseek": DEEPSEEK_MODEL_PRICES,
    "minimax": MINIMAX_MODEL_PRICES,
    "mimo": MIMO_MODEL_PRICES,
    "glm": GLM_MODEL_PRICES,
    "stepfun": STEPFUN_MODEL_PRICES,
    "gemini": GEMINI_MODEL_PRICES,
    "qwen": QWEN_MODEL_PRICES,
    "kimi": KIMI_MODEL_PRICES,
}

MODEL_PRICES: dict[str, dict[str, object]] = {
    model_key: price
    for provider_prices in PROVIDER_MODEL_PRICE_TABLES.values()
    for model_key, price in provider_prices.items()
}


MODEL_PRICE_ALIASES: dict[str, str] = {
    "chatgpt-4o-latest": "chat-latest",
    "claude-opus-4": "claude-opus-4-1",
    "claude-3-5-haiku-latest": "claude-3-5-haiku",
    "glm-4.7-flash-x": "glm-4.7-flashx",
    "qwen3-max-latest": "qwen3-max",
    "qwen-max-latest": "qwen-max",
    "qwen-plus-latest": "qwen-plus",
    "qwen-turbo-latest": "qwen-turbo",
}
