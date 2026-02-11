"""SQS-backed event bus adapter."""

from typing import Any

from ...interfaces import EventBusAdapter, EventMessage


class SqsEventBusAdapter(EventBusAdapter):
    """EventBus adapter using AWS SQS for queue operations."""

    def __init__(self, queue_name: str, sqs_client: Any) -> None:
        self.queue_name = queue_name
        self.sqs_client = sqs_client
        self.sqs_queue = self.sqs_client.get_queue_by_name(
            QueueName=self.queue_name,
        )

    def enqueue(
        self,
        message_instance: EventMessage,
        delay_seconds: int = 0,
    ) -> None:
        """Add a message to the queue."""
        self.sqs_queue.send_message(
            MessageBody=str(message_instance),
            DelaySeconds=delay_seconds,
        )

    def dequeue(self, message_instance: Any) -> None:
        """Remove a message from the queue (e.g. after successful processing)."""
        message_instance.delete()

    def get_messages(
        self,
        max_messages: int = 1,
        wait_seconds: int = 0,
        visibility_timeout: int = 60,
    ) -> Any:
        """Fetch messages from the queue."""
        return self.sqs_queue.receive_messages(
            MessageAttributeNames=["ALL"],
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_seconds,
            VisibilityTimeout=visibility_timeout,
        )
