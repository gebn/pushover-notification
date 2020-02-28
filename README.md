# Pushover Notification

[![Build Status](https://travis-ci.org/gebn/pushover-notification.svg?branch=master)](https://travis-ci.org/gebn/pushover-notification)

This lambda function supports both custom JSON strings and generic SNS messages (such as budget alerts).

## Configuration

Pushover itself is hosted in Washington D.C. by LeaseWeb, so us-east-1 is the best region from a latency perspective.

| Parameter | Value                                  |
|-----------|----------------------------------------|
| Runtime   | Python 3.7                             |
| Handler   | `pushover_notification.lambda_handler` |
| Memory    | 128 MiB (only uses ~40)                |
| Timeout   | 5 seconds                              |

## Custom

The function tries to parse all messages as custom ones in the first instance, and falls back to the generic handler if this fails.
The SNS message string should be valid JSON, parseable with `json.loads()`.
The following fields are supported:

    {
        "app": "token",               # Pushover application token
        "user": "key",                # Pushover user key
        "title": "hello",             # notification title
        "body": "human",              # message content; this is the only required field
        "timestamp": "2017-10-02",    # ISO8601 datetime; defaults to now
        "url": "https://gebn.co.uk",  # a URL to include after the body
        "url_title": "Website",       # a name for the above URL; requires it is specified
        "priority": 1                 # the integer message priority; defaults to normal
    }

## Generic

In this case, the function will pull out the `Subject`, `Message` and `Timestamp` fields and send them as if the `title`, `body` and `timestamp` fields had been specified in a custom JSON message.
