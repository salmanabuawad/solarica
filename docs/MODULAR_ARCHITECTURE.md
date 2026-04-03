# Solarica Modular Architecture (Joomla-like Extension System)

## Concept
Solarica is built as:
Core Platform + Modules

## Stack
- React (frontend)
- Python FastAPI (backend)
- PostgreSQL (DB)
- Nginx (gateway)

## Core Responsibilities
- Auth / Roles
- Projects / Assets
- Tasks / Approvals
- Files / Audit
- Event Bus
- Module Registry

## Modules
Each module includes:
- backend routes/services
- database tables
- frontend pages/components
- permissions
- event subscriptions

## Module Structure
modules/<module_name>/
  backend/
  frontend/
  manifest.json

## Manifest Example
{
  "name": "inventory",
  "version": "1.0.0",
  "dependsOn": ["projects"],
  "permissions": ["inventory.view"],
  "events": ["task.completed"]
}

## Integration Methods
1. API: /api/modules/<name>/*
2. UI: menus/pages/widgets
3. Events: subscribe/publish
4. Permissions
5. Shared services

## Event Example
measurement.imported → analytics → issue → task → notify

## Rules
Modules:
✔ use core services
✔ register via manifest
❌ bypass auth
❌ modify core directly

## Benefits
- scalable
- configurable per customer
- commercial modular pricing