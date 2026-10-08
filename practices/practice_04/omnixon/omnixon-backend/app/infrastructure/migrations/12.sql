-- How a model is reached. A model is called through OpenRouter, with the key of the deployment, through the proxy of the deployment
-- (OPENROUTER_PROXY). These say otherwise for one model:
--   base_url   another OpenAI-compatible server (a local vLLM or Ollama, a Russian provider); NULL: OpenRouter
--   use_proxy  false: call it directly, not through the proxy
--   api_token  the key for that server; NULL: the key of the deployment. A secret: never returned by the API.
ALTER TABLE models ADD COLUMN IF NOT EXISTS base_url TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS use_proxy BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE models ADD COLUMN IF NOT EXISTS api_token TEXT;
