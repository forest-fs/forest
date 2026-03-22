# LLM configuration

Forest uses the **`openai` Python SDK** with a configurable **`base_url`** and **`api_key`**. The HTTP **protocol** is the same shape OpenAI publishes (`/v1/chat/completions`, `/v1/embeddings`, …). That does **not** mean you must use OpenAI’s product — it only describes the wire format the client speaks.

You can configure the app in either of these ways:

| What you use | What you set | Typical keys / models |
|----------------|--------------|------------------------|
| **[OpenRouter](https://openrouter.ai/)** (default) | Leave **`LLM_BASE_URL`** at `https://openrouter.ai/api/v1` (or omit it). | **`LLM_API_KEY`**: OpenRouter key. **`CHAT_MODEL_ID`**: any OpenRouter slug (OpenAI, **Anthropic**, **Google**, **Mistral**, Llama, …). **`EMBEDDING_MODEL_ID`**: an embedding slug OpenRouter serves (often `openai/text-embedding-3-small`). |
| **Another OpenAI-compatible API** | Set **`LLM_BASE_URL`** to that provider’s base URL. | **`LLM_API_KEY`**: key from **that** provider (OpenAI, Mistral, Together, …). **`CHAT_MODEL_ID` / `EMBEDDING_MODEL_ID`**: IDs **they** expect (not OpenRouter slugs). |

So: **OpenRouter** is one concrete service behind an OpenAI-compatible URL. **“OpenAI-compatible”** is the general case — OpenRouter, direct OpenAI, Azure OpenAI, Ollama (with compat layer), etc.

## Environment variables

### Required (LLM)

| Variable | Alternatives | Purpose |
|----------|--------------|---------|
| `LLM_API_KEY` | `OPENROUTER_API_KEY` (legacy name; same value) | API key for **whatever** `LLM_BASE_URL` points at |
| `CHAT_MODEL_ID` | — | Chat completion model identifier (**OpenRouter slug** or **provider-native** id, depending on `LLM_BASE_URL`) |
| `EMBEDDING_MODEL_ID` | — | Embedding model identifier; **output dimension must match Postgres** |

`OPENROUTER_*` names remain supported so existing deployments keep working.

### Optional

| Variable | Alternatives | Purpose |
|----------|--------------|---------|
| `LLM_BASE_URL` | `OPENROUTER_BASE_URL` | Base URL for chat + embeddings (default: **OpenRouter** `https://openrouter.ai/api/v1`) |
| `LLM_HTTP_REFERER` | `OPENROUTER_HTTP_REFERER` | Optional `HTTP-Referer` (OpenRouter attribution when using OpenRouter) |
| `LLM_APP_NAME` | `OPENROUTER_APP_NAME` | Optional `X-Title` header (OpenRouter attribution when using OpenRouter) |

If both a legacy and a new name are set for the same field, **`LLM_*` wins** (canonical names are listed first in settings). Prefer setting **only one** name per field to avoid surprises.

## Embeddings and `vector(768)`

The database column is **`vector(768)`** (`EMBEDDING_VECTOR_DIMENSIONS`). For models that support OpenAI’s optional **`dimensions`** request field (e.g. **`text-embedding-3-small`** / **`text-embedding-3-large`**), Forest **automatically** sets `dimensions` to match the schema so you get **768**-float vectors without storing full 1536- or 3072-dim embeddings.

If your provider **does not** support `dimensions` (or returns a fixed length), pick a model whose native output length is **768**, or change `EMBEDDING_VECTOR_DIMENSIONS` + add an Alembic migration + re-embed.

## Example setups (tested patterns)

| Setup | `LLM_BASE_URL` | Example `CHAT_MODEL_ID` | Example `EMBEDDING_MODEL_ID` | Notes |
|-------|----------------|---------------------------|------------------------------|--------|
| **OpenRouter** (default) | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` | `openai/text-embedding-3-small` | OpenRouter key + slugs; embeddings use `dimensions=768`. |
| **OpenAI** direct | `https://api.openai.com/v1` | `gpt-4o-mini` | `text-embedding-3-small` | OpenAI API key; `dimensions` sent automatically. |
| **Azure OpenAI** | `https://<resource>.openai.azure.com/openai/deployments/<deployment>` | *(deployment name)* | *(embedding deployment name)* | Confirm embedding API supports the dimensions you need. |
| **Ollama** (local) | `http://localhost:11434/v1` | `llama3.2` (example) | *(an embedding model you host)* | Must expose OpenAI-compatible `/v1/embeddings`; if `dimensions` is unsupported, use a **768**-dim native model or change the schema. |

Always verify **chat + embed** succeed and `len(embedding) == EMBEDDING_VECTOR_DIMENSIONS`.

### Non-OpenAI chat models (same default: OpenRouter)

Forest only speaks **OpenAI-shaped** HTTP. You do **not** wire Anthropic/Google/Mistral **SDKs** directly — you use a gateway that maps them to `/v1/chat/completions`, or a host that already exposes that API.

The usual pattern is **[OpenRouter](https://openrouter.ai/models)** with **one** key: set **`CHAT_MODEL_ID`** to a **provider/model** slug, and keep **`EMBEDDING_MODEL_ID`** on an embedding model OpenRouter serves (often `openai/text-embedding-3-small` so **`dimensions=768`** matches the DB). Slugs change; confirm current names on OpenRouter.

| Vendor | Example `CHAT_MODEL_ID` | Typical `EMBEDDING_MODEL_ID` | Notes |
|--------|-------------------------|-------------------------------|--------|
| **Anthropic** | `anthropic/claude-3.5-sonnet` | `openai/text-embedding-3-small` | No first-party OpenAI-compatible HTTP for this client; OpenRouter (or similar) fronts Anthropic. |
| **Google** | `google/gemini-2.0-flash-001` | `openai/text-embedding-3-small` | Chat via Gemini slug; same embedding slug as other rows. |
| **Mistral** | `mistralai/mistral-small-3.1-24b-instruct-2503` | `openai/text-embedding-3-small` | Or Mistral embedding slugs on OpenRouter if listed and **768**-compatible. |
| **Meta (Llama)** | `meta-llama/llama-3.3-70b-instruct` | `openai/text-embedding-3-small` | OSS-style chat; embeddings unchanged. |
| **Cohere** | `cohere/command-r-plus` | `openai/text-embedding-3-small` | Only if the chat slug exists on OpenRouter. |
| **DeepSeek** | `deepseek/deepseek-chat` | `openai/text-embedding-3-small` | Chat routing only; embed pipeline unchanged. |

> **Embeddings from other vendors:** OpenRouter may list **Voyage**, **Cohere**, etc. If you change `EMBEDDING_MODEL_ID`, verify **vector length** and **`dimensions`** support — it must match **`vector(768)`** or you migrate the schema.

### Direct APIs (no OpenRouter) — vendors with OpenAI-compatible bases

Point **`LLM_BASE_URL`** at the vendor (not `openrouter.ai`). Use **their** API key and **their** documented model names for chat and embed. Both calls use the **same** base URL in Forest.

| Provider | `LLM_BASE_URL` (pattern) | Example chat | Example embed | Notes |
|----------|--------------------------|--------------|---------------|--------|
| **Mistral** | `https://api.mistral.ai/v1` | `mistral-small-latest` | `mistral-embed` | Check **embedding dimension** vs **768**; may need a different embed model or schema change. |
| **Together AI** | `https://api.together.xyz/v1` | *(see Together docs)* | *(embedding model id)* | Many OSS chat models; confirm which models support **embeddings** and dims. |
| **Fireworks AI** | `https://api.fireworks.ai/inference/v1` | *(see Fireworks docs)* | *(if offered)* | Same OpenAI-style surface; verify embed endpoint + dimensions. |

**Not drop-in as `LLM_BASE_URL`:** raw **Anthropic Messages API**, **Google Generative Language API**, or **AWS Bedrock** endpoints — different request shapes. Use **OpenRouter** slugs above, or run a **compat proxy** that exposes `/v1/chat/completions` and `/v1/embeddings`.

**Groq** (`https://api.groq.com/openai/v1`) fits **chat** (`llama-3.3-70b-versatile`, etc.) but **not** a usable **`/v1/embeddings`** pairing for this app’s single client. Prefer **OpenRouter** for Groq-hosted Llama **plus** embeddings in one deployment.

## Changing embedding model

Changing `EMBEDDING_MODEL_ID` is **not** a config-only switch if the new model’s output size differs from the `file_nodes.embedding` column:

1. **Dimension mismatch** — Update `EMBEDDING_VECTOR_DIMENSIONS` in code, add an **Alembic** migration to `ALTER` the `vector(N)` column, deploy, then **re-embed** all existing rows (or accept empty search until backfill).  
2. **Same dimension** — You may only need to restart the app; existing vectors were produced with the old model, so **semantic quality** may be mixed until you re-ingest or run a backfill job.

See also [Installation → Embedding dimension](installation.md#embedding-dimension) and [FAQ → embedding dimensions](faq.md#how-do-i-change-embedding-dimensions--expected-x-dimensions-not-y).

## Why we don’t use LiteLLM here

Forest intentionally uses a **thin** OpenAI-compatible client. Using **OpenRouter** or pointing **`LLM_BASE_URL`** at another vendor covers most “bring your own key” cases without an extra dependency or embedding-provider matrix inside the app.
