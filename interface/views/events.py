"""Thin DRF view for event ingestion."""

from rest_framework import status

from data.repositories import DjangoEventRepository, create_event_with_outbox
from interface.responses import success_response
from interface.serializers import EventIngestSerializer, EventResponseSerializer
from interface.use_cases import IngestEvent
from interface.views.base import ThinAPIView


class EventIngestionView(ThinAPIView):
    """Persist incoming events and durable fan-out intent."""

    event_repository_class = DjangoEventRepository
    persist_event_with_outbox = staticmethod(create_event_with_outbox)

    def post(self, request):
        tenant_id = self.get_tenant_id()
        serializer = EventIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = self.run_use_case(
            IngestEvent(
                self.event_repository_class(),
                self.persist_event_with_outbox,
            ),
            tenant_id=tenant_id,
            **serializer.validated_data,
        )
        response_serializer = EventResponseSerializer(result.event.to_dict())
        return success_response(
            response_serializer.data,
            status_code=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
            meta={"idempotent_replay": not result.created},
        )
