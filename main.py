import os
import json
import base64
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.content_encoding import ContentEncoding
from datadog_api_client.v2.model.http_log import HTTPLog
from datadog_api_client.v2.model.http_log_item import HTTPLogItem
from datadog_api_client.exceptions import ApiException

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.events_api import EventsApi
from datadog_api_client.v1.model.event_create_request import EventCreateRequest

from google import genai
from google.genai.types import GenerateContentConfig, HttpOptions, Part

client = genai.Client(http_options=HttpOptions(api_version="v1"))

response_schema = {
  "type": "object",
  "properties": {
    "aggregation_key": {
      "type": "string",
      "maxLength": 100,
      "description": "An arbitrary string to use for aggregation. Limited to 100 characters. If you specify a key, all events using that key are grouped together in the Event Stream."
    },
    "alert_type": {
      "type": "string",
      "enum": [
        "error",
        "warning",
        "info",
        "success",
        "user_update",
        "recommendation",
        "snapshot"
      ],
      "description": "If an alert event is enabled, set its type. For example, error, warning, info, success, user_update, recommendation, and snapshot."
    },
    "date_happened": {
      "type": "integer",
      "format": "int64",
      "description": "POSIX timestamp of the event. Must be sent as an integer (that is no quotes). Limited to events no older than 18 hours"
    },
    "device_name": {
      "type": "string",
      "description": "A device name."
    },
    "host": {
      "type": "string",
      "description": "Host name to associate with the event. Any tags associated with the host are also applied to this event."
    },
    "priority": {
      "type": "string",
      "enum": [
        "normal",
        "low"
      ],
      "description": "The priority of the event. For example, normal or low."
    },
    "related_event_id": {
      "type": "integer",
      "format": "int64",
      "description": "ID of the parent event. Must be sent as an integer (that is no quotes)."
    },
    "source_type_name": {
      "type": "string",
      "description": "The type of event being posted. Option examples include nagios, hudson, jenkins, my_apps, chef, puppet, git, bitbucket, etc."
    },
    "tags": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "A list of tags to apply to the event."
    },
    "text": {
      "type": "string",
      "maxLength": 4000,
      "description": "The body of the event. Limited to 4000 characters. The text supports markdown. To use markdown in the event text, start the text block with %%% \\n and end the text block with \\n %%%."
    },
    "title": {
      "type": "string",
      "description": "The event title."
    }
  },
  "required": [
    "text",
    "title"
  ]
}

prompt = """You are a helpful assistant that processes Pub/Sub messages and generates structured JSON output.

You will receive a Pub/Sub message in JSON format. Your task is to extract relevant information from this message and format it into a JSON object that conforms to the schema.

Here are the rules you must follow:
- The output must be a valid JSON object.
- The output must conform to the response_schema.
- Ensure that the data types and constraints specified in the schema are strictly followed.
- If the pubsub message is not valid json, return an error message.

Now, process the following Pub/Sub message:

{actual_pubsub_message}
"""

def send_event_to_datadog(event, context):
    """
    PubSub trigger that sends a message payload as a Datadog event using the datadog_api_client v1 library.
    """

    # Retrieve Datadog API key and application key from environment variables
    api_key = os.environ.get('DATADOG_API_KEY')
    app_key = os.environ.get('DATADOG_APP_KEY')

    if not os.environ.get("DD_API_KEY"):
        print("Error: DD_API_KEY environment variable not set.")
        return 'Error: Missing Datadog API keys', 400

    try:
        configuration = Configuration()
        configuration.api_key["api_key"] = api_key
        configuration.api_key["app_key"] = app_key

        with ApiClient(configuration) as api_client:
            api_instance = EventsApi(api_client)

            # Decode the Pub/Sub message
            if "data" in event:
                pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
                message_data = json.loads(pubsub_message)
                print(f"Decoded Pub/Sub message: {message_data}")
            else:
                message_data = event

            # Gemini parse event to Datadog Event format
            gemini_response = client.models.generate_content(
                model="gemini-2.0-flash-lite-001",
                contents=prompt.format(actual_pubsub_message=json.dumps(message_data)),
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )

            print(f"Gemini response:\n{gemini_response.text}")
            
            if gemini_response.text:
                gemini_response_json = json.loads(gemini_response.text)
            else:
                raise ValueError("Gemini response is empty")

            # Extract event data from Gemini response
            title = gemini_response_json.get('title')
            text = gemini_response_json.get('text')
            tags = gemini_response_json.get('tags', [])
            alert_type = gemini_response_json.get('alert_type', 'info')
            aggregation_key = gemini_response_json.get('aggregation_key')
            date_happened = gemini_response_json.get('date_happened')
            device_name = gemini_response_json.get('device_name')
            host = gemini_response_json.get('host')
            priority = gemini_response_json.get('priority')
            related_event_id = gemini_response_json.get('related_event_id')
            source_type_name = gemini_response_json.get('source_type_name')

            # Construct the Datadog event request
            body = EventCreateRequest(
                title=title,
                text=text,
                tags=tags,
                alert_type=alert_type,
                aggregation_key=aggregation_key,
                date_happened=date_happened,
                device_name=device_name,
                host=host,
                priority=priority,
                related_event_id=related_event_id,
                source_type_name=source_type_name,
            )

            # Send the event to Datadog
            response = api_instance.create_event(body=body)

            print(f"Datadog event sent successfully. Response: {response}")
            print(f"Response: {response}")
            print(f"Body: {body}")

            return 'OK', 202

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except ApiException as e:
        print(f"Error sending log to Datadog: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def send_log_to_datadog(event, context):
    """
    Sends a log message to Datadog using the datadog_api_client, triggered by Pub/Sub.

    Args:
        event (dict): The dictionary with data specific to this type of
            event. The `data` field contains the PubsubMessage message. The
            `attributes` field will contain custom attributes if there are any.
        context (google.cloud.functions.Context): The Cloud Functions event
            metadata. The `event_id` field contains the Pub/Sub message ID. The
            `timestamp` field contains the publish time.
    """

    if not os.environ.get("DD_API_KEY"):
        print("Error: DD_API_KEY environment variable not set.")
        return 'Error: Missing Datadog API keys', 400

    try:
        # Decode the Pub/Sub message
        if "data" in event:
            pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
            message_data = json.loads(pubsub_message)
            print(f"Decoded Pub/Sub message: {message_data}")
        else:
            message_data = event

        configuration = Configuration()

        with ApiClient(configuration) as api_client:
            api_instance = LogsApi(api_client)

            # Prepare the log message
            log_message = json.dumps(message_data)

            # Create the log item with direct JSON format
            log_item = HTTPLogItem(
                message=pubsub_message,
                ddsource="pubsub",
                ddtags=f"env:production,function:{context.function_name if hasattr(context, 'function_name') else 'local-test'}",
                hostname=context.resource.get("name", "unknown") if hasattr(context, 'resource') else "local-test",
                service="gcp",
                status=message_data.get("level", "info").lower(),
                user=message_data.get("user"),
                event_id=message_data.get("event_id"),
            )

            # Create the HTTP log payload
            body = HTTPLog([log_item])

            # Send the log to Datadog
            response = api_instance.submit_log(
                body=body,
            )
            print(f"Successfully sent log to Datadog")
            print(f"Response: {response}")
            print(f"Body: {body}")

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except ApiException as e:
        print(f"Error sending log to Datadog: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Example usage:
if __name__ == "__main__":
    class MockContext:
        """Mock class to simulate the Cloud Functions context object."""
        def __init__(self, function_name, resource):
            self.function_name = function_name
            self.resource = resource
    
    class MockResource:
        """Mock class to simulate the Cloud Functions resource object."""
        def __init__(self, name):
            self.name = name
        def get(self, key, default):
            return self.name

    log_data = {
        "timestamp": "2023-10-27T10:00:00Z",
        "level": "INFO",
        "message": "This is a local test log message.",
        "user": "testuser",
        "event_id": "12345"
    }

    # Test with a Pub/Sub event (simulated)
    pubsub_event = {
        "data": base64.b64encode(json.dumps(log_data).encode("utf-8")).decode("utf-8")
    }
    mock_context = MockContext(
        "pubsub-test-function", MockResource("pubsub-test-resource")
    )
    send_log_to_datadog(pubsub_event, mock_context)

    # Local test
    body = HTTPLog(
        [
            HTTPLogItem(
                ddsource="nginx",
                ddtags="env:staging,version:5.1",
                hostname="i-012345678",
                message="2019-11-19T14:37:58,995 INFO [process.name][20081] Hello World",
                service="payment",
                status="info",
            ),
        ]
    )
    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api_instance = LogsApi(api_client)
        response = api_instance.submit_log(body=body)

        print(response)
        print(body)

    # Test send event
    event_data = {
        "title": "Test Event",
        "text": "This is a test event from local.",
        "tags": ["test", "local"],
        "alert_type": "warning",
        "priority": "low"
    }
    pubsub_event = {
        "data": base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
    }
    send_event_to_datadog(pubsub_event, mock_context)