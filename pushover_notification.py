# -*- coding: utf-8 -*-
from typing import Dict, Callable, Any
import logging
import os
import functools
import dateutil.parser
import json
import pullover
from pullover import Application, User, Message

_DEFAULT_PUSHOVER_APP_TOKEN = os.environ['DEFAULT_PUSHOVER_APP_TOKEN']
_DEFAULT_PUSHOVER_USER_KEY = os.environ['DEFAULT_PUSHOVER_USER_KEY']

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger('pullover').setLevel(logging.DEBUG)


def _extract(payload: Dict[str, Any], key: str, default: Any = None,
             process: Callable[[Any], Any] = lambda i: i):
    """
    Pull a variable out of a payload.

    :param payload: The payload dictionary.
    :param key: The name of the key to retrieve from the payload.
    :param default: The value to return if the key is not in the payload.
                    Defaults to None.
    :param process: If the key is in the payload, the corresponding value is
                    passed through this function before being returned. This
                    function will propagate any errors raised by this callable.
                    Defaults to an identity function, i.e. no processing.
    :return: The processed value under the key, or the default if the key was
             not passed.
    """
    # this seems trivial, and it is, but we've had a bug caused by one key
    # being checked and a different one retrieved, resulting in a KeyError
    if key in payload:
        return process(payload[key])
    return default


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
        raise ValueError(f'Message is not valid JSON') from e

    if 'body' not in message:
        raise ValueError('Message must have a body')
    body = message['body']

    extract = functools.partial(_extract, message)
    app_token = extract('app', _DEFAULT_PUSHOVER_APP_TOKEN)
    user_key = extract('user', _DEFAULT_PUSHOVER_USER_KEY)
    title = extract('title')
    timestamp = extract('timestamp', process=dateutil.parser.parse)
    url = extract('url')
    url_title = extract('url_title')
    priority = extract('priority')

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

    extract = functools.partial(_extract, sns)
    title = extract('Subject')
    timestamp = extract('Timestamp', process=dateutil.parser.parse)

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

    logger.debug('Parsing message %s', sns['MessageId'])

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
        logger.warning('Failed to parse message as JSON; falling back to '
                       'generic handler')
        return _parse_generic_message(record)


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    """
    AWS Lambda entry point.

    :param event: The event that triggered this execution.
    :param context: Current runtime information: http://docs.aws.amazon.com
                    /lambda/latest/dg/python-context-object.html.
    :raises RuntimeError: If a problem occurs during execution.
    """
    logger.info('Event: %s', json.dumps(event, indent=4))

    if 'Records' not in event or not event['Records']:
        raise RuntimeError('Event contains no records')

    record = event['Records'][0]  # there will never be more than one record
    message = _parse_message(record)
    response = message.send(max_tries=1)  # disable back-off - use Lambda retry
    if not response.ok:
        raise RuntimeError(f'Send error {response.status} for request '
                           f'{response.id}: {response.errors}')

    logger.info('Successfully sent notification %s', response.id)
