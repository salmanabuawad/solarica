# Architecture

PVPM Device -> USB -> Local Reader Service -> React UI / Backend API -> PostgreSQL

The local reader is responsible for hardware communication, caching raw payloads, and syncing normalized measurements.
