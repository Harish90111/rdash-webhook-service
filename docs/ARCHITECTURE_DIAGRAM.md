# Architecture Diagram

This document gives a graphical view of the webhook delivery service from three
angles:

- Clean Architecture layer boundaries
- runtime event-to-webhook flow
- local deployment topology

## 1. Layered Architecture

```mermaid
flowchart LR
    Producer["Producer / Integrator"]
    Admin["Ops / Admin User"]

    subgraph Interface["Interface Layer"]
        Views["DRF Views / Serializers"]
        Auth["API Key Authentication"]
        Tasks["Celery Task Entry Points"]
        AdminUI["Django Admin"]
    end

    subgraph Domain["Domain Layer"]
        UseCases["Use Cases"]
        Entities["Entities / Value Objects"]
        Rules["Matching / Signing / Retry Policy"]
        Ports["Repository + Gateway Interfaces"]
    end

    subgraph Data["Data Layer"]
        Repos["ORM Repositories"]
        Models["Django Models / Migrations"]
        Gateway["HTTP Gateway"]
        Security["Secret Encryption"]
        Monitoring["Metrics / Structured Logging"]
    end

    subgraph Infra["Infrastructure"]
        Postgres[("PostgreSQL")]
        Redis[("Redis / Celery Broker")]
        Target["Webhook Target"]
    end

    Producer --> Views
    Admin --> AdminUI
    Views --> UseCases
    Auth --> UseCases
    Tasks --> UseCases
    AdminUI --> Repos

    UseCases --> Ports
    Repos --> Ports
    Gateway --> Ports

    Repos --> Models
    Repos --> Postgres
    Gateway --> Target
    Tasks --> Redis
    Monitoring --> Postgres
    Security --> Postgres

    classDef layer fill:#eef3ff,stroke:#4f6fd8,stroke-width:1px,color:#111;
    class Interface,Domain,Data,Infra layer;
```

## 2. Runtime Delivery Flow

```mermaid
sequenceDiagram
    participant Producer as Producer
    participant API as Django / DRF API
    participant UC as Domain Use Case
    participant DB as PostgreSQL
    participant Beat as Celery Beat
    participant Worker as Celery Worker
    participant Redis as Redis Broker
    participant Target as Webhook Target

    Producer->>API: POST /api/events/
    API->>UC: IngestEvent
    UC->>DB: Persist event + outbox row (single transaction)
    DB-->>API: committed event
    API-->>Producer: 201 Created

    Beat->>Redis: schedule dispatch_outbox_batch
    Redis->>Worker: dispatch_outbox_batch task
    Worker->>DB: lock pending outbox rows
    Worker->>Redis: enqueue fanout_event
    Worker->>DB: mark outbox published

    Redis->>Worker: fanout_event task
    Worker->>DB: load event + active subscriptions
    Worker->>Worker: wildcard match by tenant/event type
    Worker->>DB: create unique delivery attempts
    Worker->>Redis: enqueue deliver_webhook per subscription

    Redis->>Worker: deliver_webhook task
    Worker->>DB: claim delivery attempt atomically
    Worker->>Target: signed HTTP POST

    alt 2xx response
        Target-->>Worker: success
        Worker->>DB: mark success
    else timeout / 4xx / 5xx
        Target-->>Worker: failure
        Worker->>Worker: retry policy + circuit breaker
        Worker->>DB: mark retrying / dead_letter
        Worker->>Redis: schedule retry when eligible
    end
```

## 3. Local Deployment Topology

```mermaid
flowchart TB
    subgraph DevHost["Developer Machine"]
        VSCode["VS Code / Debugger"]

        subgraph Compose["Docker Compose"]
            Web["web\nDjango + DRF + debugpy"]
            Worker["celery-worker\ndelivery + fan-out + outbox dispatch"]
            Beat["celery-beat\nperiodic scheduler"]
            Pg[("postgres")]
            R[("redis")]
        end

        Browser["Browser / Swagger / Admin"]
        WebhookSite["Webhook Receiver / webhook.site"]
    end

    Browser --> Web
    Web --> Pg
    Web --> R
    Worker --> Pg
    Worker --> R
    Beat --> R
    Worker --> WebhookSite

    VSCode -. attach :5678 .-> Web
    VSCode -. attach :5680 .-> Worker
    VSCode -. attach :5681 .-> Beat
```

## 4. Reading Guide

- `Interface -> Domain <- Data` is the key dependency rule.
- PostgreSQL is the source of truth for events, subscriptions, attempts, and
  outbox rows.
- Redis/Celery handles asynchronous execution, not durable event ownership.
- The outbox table is what protects the system from losing accepted events if
  the broker is temporarily unavailable.
