"""Monitoring-oriented data services for health and metrics snapshots."""

import time

from django.conf import settings
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone

from data.models.models import (
    DeliveryAttempt,
    DeliveryStatus,
    OutboxMessage,
    OutboxStatus,
    Subscription,
    WebhookEvent,
)


SERVICE_NAME = "rdash-webhook-service"
SERVICE_VERSION = "v1"


class ServiceHealthService:
    """Build a lightweight health snapshot for operational checks."""

    def snapshot(self):
        database = self._database_check()
        broker = self._broker_check()
        overall_status = "ok" if database["status"] == "ok" and broker["status"] == "ok" else "degraded"
        return {
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "environment": getattr(settings, "APP_ENV", "development"),
            "status": overall_status,
            "timestamp": timezone.now().isoformat(),
            "checks": {
                "database": database,
                "broker": broker,
            },
        }

    @staticmethod
    def _broker_check():
        broker_url = str(getattr(settings, "CELERY_BROKER_URL", "")).strip()
        if not broker_url:
            return {
                "status": "error",
                "mode": "configuration",
                "detail": "CELERY_BROKER_URL is not configured.",
            }
        transport = broker_url.split("://", 1)[0]
        return {
            "status": "ok",
            "mode": "configuration",
            "transport": transport,
        }

    @staticmethod
    def _database_check():
        started_at = time.perf_counter()
        try:
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {
                "status": "ok",
                "vendor": connection.vendor,
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
            }
        except Exception as exc:
            return {
                "status": "error",
                "vendor": connection.vendor,
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "error": exc.__class__.__name__,
                "detail": str(exc),
            }


class TenantMetricsService:
    """Build tenant-scoped operational metrics from persisted data."""

    def snapshot(self, tenant_id: str):
        subscription_counts = Subscription.objects.filter(tenant_id=tenant_id).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(active=True)),
        )
        event_counts = WebhookEvent.objects.filter(tenant_id=tenant_id).aggregate(
            received=Count("id"),
            processed=Count("id", filter=Q(processed=True)),
        )
        delivery_counts = self._delivery_counts(tenant_id)
        outbox_counts = OutboxMessage.objects.filter(tenant_id=tenant_id).aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=OutboxStatus.PENDING)),
            in_progress=Count("id", filter=Q(status=OutboxStatus.IN_PROGRESS)),
            published=Count("id", filter=Q(status=OutboxStatus.PUBLISHED)),
            failed=Count("id", filter=Q(status=OutboxStatus.FAILED)),
        )

        received_events = event_counts["received"] or 0
        processed_events = event_counts["processed"] or 0
        completed_deliveries = delivery_counts["success"] + delivery_counts["dead_letter"]
        success_rate = round((delivery_counts["success"] / completed_deliveries) * 100, 2) if completed_deliveries else 0.0
        failure_rate = round((delivery_counts["dead_letter"] / completed_deliveries) * 100, 2) if completed_deliveries else 0.0

        return {
            "tenant_id": str(tenant_id),
            "captured_at": timezone.now().isoformat(),
            "subscriptions": {
                "total": subscription_counts["total"] or 0,
                "active": subscription_counts["active"] or 0,
            },
            "events": {
                "received": received_events,
                "processed": processed_events,
                "pending": max(received_events - processed_events, 0),
            },
            "deliveries": {
                "total": delivery_counts["total"],
                "completed": completed_deliveries,
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "by_status": {
                    "pending": delivery_counts["pending"],
                    "in_progress": delivery_counts["in_progress"],
                    "success": delivery_counts["success"],
                    "failed": delivery_counts["failed"],
                    "retrying": delivery_counts["retrying"],
                    "dead_letter": delivery_counts["dead_letter"],
                },
            },
            "outbox": {
                "total": outbox_counts["total"] or 0,
                "backlog": (outbox_counts["pending"] or 0)
                + (outbox_counts["in_progress"] or 0)
                + (outbox_counts["failed"] or 0),
                "by_status": {
                    "pending": outbox_counts["pending"] or 0,
                    "in_progress": outbox_counts["in_progress"] or 0,
                    "published": outbox_counts["published"] or 0,
                    "failed": outbox_counts["failed"] or 0,
                },
            },
        }

    @staticmethod
    def _delivery_counts(tenant_id: str):
        summary = DeliveryAttempt.objects.filter(
            event__tenant_id=tenant_id,
            subscription__tenant_id=tenant_id,
        ).aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=DeliveryStatus.PENDING)),
            in_progress=Count("id", filter=Q(status=DeliveryStatus.IN_PROGRESS)),
            success=Count("id", filter=Q(status=DeliveryStatus.SUCCESS)),
            failed=Count("id", filter=Q(status=DeliveryStatus.FAILED)),
            retrying=Count("id", filter=Q(status=DeliveryStatus.RETRYING)),
            dead_letter=Count("id", filter=Q(status=DeliveryStatus.DEAD_LETTER)),
        )
        return {key: value or 0 for key, value in summary.items()}
