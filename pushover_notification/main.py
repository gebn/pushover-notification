# -*- coding: utf-8 -*-
from typing import Tuple
import logging
import dateutil.parser
import json
import pullover
from pullover import Application, User, Message
import os

import util

_DEFAULT_PUSHOVER_APP_TOKEN = util.kms_decrypt_str(
    os.environ['DEFAULT_PUSHOVER_APP_TOKEN'])
_DEFAULT_PUSHOVER_USER_KEY = util.kms_decrypt_str(
    os.environ['DEFAULT_PUSHOVER_USER_KEY'])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _parse_json_message(record: dict) -> pullover.PreparedMessage:
    """
    Extract a JSON-formatted message from an SNS record. This allows more
    control over the notification, but requires the sender to be familiar with
    our format.

    :param record: The the Lambda event record. This should be a message from
                   SNS.
    :return: A Pushover app, user, message tuple constructed from the event.
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
    url_title = message['url_title'] if 'url_title' in message else None
    priority = message['priority'] if 'url' in message else None

    return Message(body, title, timestamp, url, url_title, priority).prepare(
        Application(app_token), User(user_key))


def _parse_generic_message(record: dict) -> pullover.PreparedMessage:
    """
    Extract a simple message from an event. This simply uses the `Subject`,
    `Message` and `Timestamp` fields of the SNS notification.

    :param record: The the Lambda event record. This should be a message from
                   SNS.
    :return: A Pushover app, user, message tuple constructed from the event.
    :raises ValueError: If the event is malformed.
    """

    sns = record['Sns']
    title = sns['Subject'] if 'Subject' in sns else None
    timestamp = dateutil.parser.parse(sns['Timestamp']) \
        if 'Timestamp' in sns else None

    return Message(sns['Message'], title, timestamp).prepare(
        Application(_DEFAULT_PUSHOVER_APP_TOKEN),
        User(_DEFAULT_PUSHOVER_USER_KEY))


def _parse_message(record: dict) -> pullover.PreparedMessage:
    """
    Turn an event record into a Pushover message.

    :param record: The JSON-formatted, or plaintext event.
    :return: A Pushover app, user, message tuple constructed from the event.
    :raises ValueError: If the event is malformed.
    """
    if 'Sns' not in record:  # could also check EventSource == 'aws:sns'
        raise ValueError('Event did not originate from SNS')

    sns = record['Sns']
    if 'Type' not in sns or sns['Type'] != 'Notification':
        raise ValueError('Event is not an SNS notification')

    if 'MessageId' not in sns:
        raise ValueError('SNS notification lacks a MessageId')

    logger.info('Parsing message %s', sns['MessageId'])

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
    logger.info('Event: %s', json.dumps(event, indent=4))

    if 'Records' not in event:
        logger.error('Event contains no records')
        return 1

    errors = 0
    for record in event['Records']:
        try:
            message = _parse_message(record)
            response = message.send(max_tries=1)  # disable back-off
            if not response.ok:
                logger.error('Send error %d for request %s: %s',
                             response.status, response.id, response.errors)
                errors += 1
                continue

            logger.debug('Successfully sent notification %s', response.id)
        except ValueError:
            logger.exception('Malformed event record')
            errors += 1

    return errors
