# Solarica — Claude Handoff Guide

## Product
**Solarica — From Design to Operation**

Solarica is a full lifecycle solar project platform that covers:
- design intake and validation
- implementation tracking
- testing and commissioning
- maintenance
- inventory and warehouse control
- material accountability and red flags
- role-based mobile workflows
- PVPM measurement ingestion

## Priority Principles
1. Everything is project-scoped.
2. Design validation is mandatory before project approval.
3. Field workflows are role-based and mobile-first.
4. Measurements, tasks, inventory, and approvals must stay linked.
5. Solarica is the source of truth even when integrating with Monday.

## Current Bundle Contents
- `database/solarica_schema.sql` — starter SQL schema
- `backend/` — FastAPI skeleton with routes for projects, tasks, measurements, inventory, mobile, branding
- `mobile-ui/` — mobile view specs and starter screens
- `docs/FINAL_PRODUCT_DEFINITION_V5.md` — product definition

## What Claude Should Build Next
### Backend
- replace in-memory services with PostgreSQL repositories
- add auth and role permissions
- add file upload support for attachments and test evidence
- implement design validation engine
- implement warehouse transaction reconciliation
- implement red flag scheduled job

### Frontend
- build New Project wizard
- build Open Project dashboard
- build Inventory / Warehouse screens
- build role-based mobile web views
- connect frontend to backend API

### Measurements
- improve PVPM parser
- link measurements to tasks and test results
- support import of `.SUI` and validated `.XLS`

## Naming / Branding
Use these consistently:
- Product: `Solarica`
- Tagline: `From Design to Operation`
- Positioning: `The Solar Operating System`

## Coding Preferences
- prefer clear modular structure
- keep business logic in services
- use typed schemas
- avoid hard-coded naming patterns; keep them project-configurable
- preserve auditability for approvals, inventory, and task communication

## Suggested Build Order
1. auth + users + roles
2. project + validation
3. tasks + messages + approvals
4. inventory + warehouse + red flags
5. measurements + tests
6. mobile workflows
7. Monday integration
