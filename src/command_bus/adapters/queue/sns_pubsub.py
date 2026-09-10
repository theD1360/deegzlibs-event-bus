"""SNS fan-out adapter with SQS subscription for EventBus workers."""

from __future__ import annotations

import json
from typing import Any, List, Optional, Type

from ...interfaces import QueueAdapter, TransmissibleBaseModel
from ...parsers import MessageParserBase


def _unwrap_sns_message(sqs_body: str) -> str:
    """Extract the event payload from an SNS-to-SQS notification envelope."""
    try:
        envelope = json.loads(sqs_body)
    except (json.JSONDecodeError, TypeError):
        return sqs_body
    if envelope.get("Type") == "Notification" and "Message" in envelope:
        return envelope["Message"]
    return sqs_body


class _SnsPubSubMessage:
    """Wrapper so SNS/SQS messages have .body and .delete()."""

    __slots__ = ("body", "_sqs_message")

    def __init__(self, body: str, sqs_message: Any) -> None:
        self.body = body
        self._sqs_message = sqs_message

    def delete(self) -> None:
        self._sqs_message.delete()


class SnsPubSubAdapter(QueueAdapter):
    """
    Fan-out adapter using AWS SNS with per-worker SQS subscriptions.

    ``enqueue`` publishes to ``topic_arn`` using an optional
    :class:`~command_bus.parsers.MessageParserBase` for serialization
    (``dumps``, ``subject``, ``message_attributes``). Each adapter instance
    polls its own ``queue_url`` when consuming (SQS queue subscribed to the
    topic), so every worker receives a copy of each event.

    For publish-only use (e.g. outbound notifications), omit ``queue_url``
    and ``sqs_client``.

    Requires ``pip install deegzlibs-command-bus[sns]`` (boto3).
    """

    def __init__(
        self,
        topic_arn: str,
        sns_client: Any,
        sqs_client: Any = None,
        queue_url: Optional[str] = None,
        message_parser_class: Optional[Type[MessageParserBase]] = None,
    ) -> None:
        self.queue_name = topic_arn
        self._topic_arn = topic_arn
        self._sns_client = sns_client
        self.message_parser_class = message_parser_class
        if sqs_client is not None and queue_url is not None:
            self._sqs_queue = sqs_client.Queue(queue_url)
        elif sqs_client is None and queue_url is None:
            self._sqs_queue = None
        else:
            raise ValueError("Provide both sqs_client and queue_url, or neither")

    def bind_message_parser(
        self,
        message_parser_class: Type[MessageParserBase],
    ) -> None:
        """Set the parser used for publish serialization and metadata."""
        self.message_parser_class = message_parser_class

    def _encode_for_publish(
        self,
        message_instance: TransmissibleBaseModel,
    ) -> tuple[str, dict[str, Any]]:
        if self.message_parser_class is None:
            return str(message_instance), {}

        parser_class = self.message_parser_class
        body = parser_class.dumps(message_instance)
        publish_kwargs: dict[str, Any] = {}

        subject = parser_class.subject(message_instance, body)
        if subject is not None:
            publish_kwargs["Subject"] = subject

        attributes = parser_class.message_attributes(message_instance, body)
        if attributes is not None:
            publish_kwargs["MessageAttributes"] = attributes

        return body, publish_kwargs

    def _publish(
        self,
        message_instance: TransmissibleBaseModel,
    ) -> None:
        body, publish_kwargs = self._encode_for_publish(message_instance)
        kwargs = {"Message": body, **publish_kwargs}

        topic_arn = getattr(self._sns_client, "topic_arn", None)
        if isinstance(topic_arn, str) and topic_arn.startswith("arn:aws:sns"):
            self._sns_client.publish(**kwargs)
            return
        self._sns_client.publish(TopicArn=self._topic_arn, **kwargs)

    def enqueue(
        self,
        message_instance: TransmissibleBaseModel,
        delay_seconds: int = 0,
    ) -> None:
        """Publish to the SNS topic. delay_seconds is ignored."""
        self._publish(message_instance)

    def dequeue(self, message_instance: Any) -> None:
        if hasattr(message_instance, "delete"):
            message_instance.delete()

    def get_messages(
        self,
        max_messages: int = 1,
        wait_seconds: int = 0,
        visibility_timeout: int = 60,
        **kwargs: Any,
    ) -> List[_SnsPubSubMessage]:
        """Poll this worker's SQS queue for SNS-delivered events."""
        if self._sqs_queue is None:
            raise RuntimeError(
                "sqs_client and queue_url are required to consume messages"
            )
        raw_messages = self._sqs_queue.receive_messages(
            MessageAttributeNames=["ALL"],
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_seconds,
            VisibilityTimeout=visibility_timeout,
        )
        return [
            _SnsPubSubMessage(
                body=_unwrap_sns_message(msg.body),
                sqs_message=msg,
            )
            for msg in raw_messages
        ]
