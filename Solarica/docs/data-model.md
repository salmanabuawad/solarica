# Data Model Overview

## Core hierarchy

- site
  - project
    - section
      - inverter
        - string
          - panel_group
      - cable_path

## Key tables

### Security / users
- users
- roles
- user_global_roles
- user_project_roles

### Master / project
- sites
- projects
- project_stage_history
- sections
- inverters
- strings
- panel_groups
- cable_paths
- equipment_models

### Design ingestion
- design_files
- parser_runs
- parsed_entities
- parser_attachments

### Validation
- validation_rules
- validation_rule_parameters
- validation_rule_overrides
- validation_runs
- validation_issues
- validation_exceptions

### Construction
- work_packages
- daily_progress_reports
- progress_items
- field_attachments

### Inventory
- inventory_items
- inventory_balances
- inventory_transactions

### Testing
- test_types
- test_records
- test_attachments
- commissioning_checklists

### O&M
- maintenance_plans
- maintenance_events
- periodic_test_schedules
