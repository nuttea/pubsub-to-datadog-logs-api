import os
import json
import base64
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.content_encoding import ContentEncoding
from datadog_api_client.v2.model.http_log import HTTPLog
from datadog_api_client.v2.model.http_log_item import HTTPLogItem
from datadog_api_client.exceptions import ApiException

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
        return

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
                message=pubsub_message,  # Sending the entire Pub/Sub message for detailed logging
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
