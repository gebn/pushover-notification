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


def _parse_message(record: dict) -> chump.Message:
    """
    Extract a Pushover message from an SNS record.
    
    :param record: The individual SNS record. 
    :return: The Pushover message.
    :raises ValueError: If the message is malformed.
    """
    message = json.loads(record['Sns']['Message'])
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
    for record in event['Records']:
        try:
            message = _parse_message(record)
            message.send()
            if not message.is_sent:
                return 2
            logger.debug('Successfully sent notification %s', message.id)
        except (ValueError, KeyError):
            logger.exception('Malformed message')
    return 0
