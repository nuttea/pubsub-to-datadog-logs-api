# pubsub-to-datadog-logs-api
Google Cloud PusSub message to Datadog Logs API using Cloud Functions

## Preparation

Create a python virtual environment

```
python --version
python -m venv .venv
source .venv/bin/activate
```

(Optional) If you would like to update dependencies

```
pip install pip-tools
pip-compile
```

Install packages in venv

```
pip install -r requirements.txt
```

Set ENV VARS, required for DD_API_KEY and DD_SITE

```
export DD_SITE="datadoghq.com"
export DD_API_KEY="<DD_API_KEY>"
```

(Optional) Crawl Datadog Docs for Logs API for Gemini Code Assist context, this improve code suggestion on developments.

```
curl https://r.jina.ai/https://docs.datadoghq.com/api/latest/logs/   -H "X-Return-Format: markdown" > docs-datadog-api-logs.md
```

## Deploy to Cloud Run Functions

```
export FUNCTION_NAME=nuttee-alerts-to-datadog-logs-api
export PUBSUB_TOPIC=nuttee-alerts-to-pubsub
export REGION=us-central1
gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime=python312 \
  --source=. \
  --entry-point=send_log_to_datadog \
  --trigger-topic=$PUBSUB_TOPIC \
  --region=us-central1 \
  --set-env-vars=DD_SITE=$DD_SITE,DD_API_KEY=$DD_API_KEY
```