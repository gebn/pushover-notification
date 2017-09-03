# -*- coding: utf-8 -*-
import logging
import dateutil.parser
import json
import chump
import os

import util

_DEFAULT_PUSHOVER_APP_TOKEN = util.kms_decrypt_str(
    os.environ['DEFAULT_PUSHOVER_APP_TOKEN'])
_DEFAULT_PUSHOVER_USER_KEY = util.kms_decrypt_str(
    os.environ['DEFAULT_PUSHOVER_USER_KEY'])

logging.getLogger('chump').setLevel(logging.INFO)  # chump is very loud
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _parse_json_message(record: dict) -> chump.Message:
    """
    Extract a JSON-formatted message from an SNS record. This allows more
    control over the notification, but requires the sender to be familiar with
    our format.

    :param record: The the Lambda event record. This should be a message from
                   SNS.
    :return: A Pushover message constructed from the event.
    :raises ValueError: If the event or message is malformed.
    """

    try:
        message = json.loads(record['Sns']['Message'])
    except json.decoder.JSONDecodeError as e:
        raise ValueError(f'Message is not valid JSON: {e}')

    if 'body' not in message:
        raise ValueError('Message must have a body')

    app_token = message['app'] \
        if 'app' in message else _DEFAULT_PUSHOVER_APP_TOKEN
    user_key = message['user'] \
        if 'user' in message else _DEFAULT_PUSHOVER_USER_KEY
    body = message['body']
    title = message['title'] if 'title' in message else None
    timestamp = dateutil.parser.parse(message['timestamp']) \
        if 'timestamp' in message else None
    url = message['url'] if 'url' in message else None
    priority = message['priority'] if 'url' in message else None

    user = chump.Application(app_token).get_user(user_key)
    return user.create_message(body, title=title, timestamp=timestamp, url=url,
                               priority=priority)


def _parse_generic_message(record: dict) -> chump.Message:
    """
    Extract a simple message from an event. This simply uses the `Subject`,
    `Message` and `Timestamp` fields of the SNS notification.

    :param record: The the Lambda event record. This should be a message from
                   SNS.
    :return: A Pushover message constructed from the event.
    :raises ValueError: If the event is malformed.
    """

    sns = record['Sns']
    title = sns['Subject'] if 'Subject' in sns else None
    timestamp = sns['Timestamp'] if 'Timestamp' in sns else None

    user = chump \
        .Application(_DEFAULT_PUSHOVER_APP_TOKEN) \
        .get_user(_DEFAULT_PUSHOVER_USER_KEY)
    return user.create_message(sns['Message'], title=title,
                               timestamp=timestamp)


def _parse_message(record: dict) -> chump.Message:
    """
    Turn an event record into a Pushover message.

    :param record: The JSON-formatted, or plaintext event.
    :return: A Pushover message constructed from the event.
    :raises ValueError: If the event is malformed.
    """
    if 'Sns' not in record:  # could also check EventSource == 'aws:sns'
        raise ValueError('Event did not originate from SNS')

    sns = record['Sns']
    if 'Type' not in sns or sns['Type'] != 'Notification':
        raise ValueError('Event is not an SNS notification')

    if 'Message' not in sns:
        raise ValueError('SNS notification lacks a Message')

    try:
        # attempt to parse the event as a JSON-formatted message; this will
        # work for events sent by applications aware of our existence
        return _parse_json_message(record)
    except ValueError:
        # fall back to creating a notification from the raw event fields; this
        # will be used for events from AWS itself, e.g. when a budget is
        # exceeded
        return _parse_generic_message(record)


# noinspection PyUnusedLocal
def lambda_handler(event, context) -> int:
    """
    AWS Lambda entry point.

    :param event: The event that triggered this execution.
    :param context: Current runtime information: http://docs.aws.amazon.com
                    /lambda/latest/dg/python-context-object.html.
    :return: The script exit code.
    """
    logger.info(f'Event: {event}')

    if 'Records' not in event:
        logger.error('Event contains no records')
        return 1

    errors = 0
    for record in event['Records']:
        try:
            message = _parse_message(record)
            message.send()
            if not message.is_sent:
                errors += 1
                continue

            logger.debug(f'Successfully sent notification {message.id}')
        except ValueError:
            logger.exception('Malformed event record')
            errors += 1

    return errors
