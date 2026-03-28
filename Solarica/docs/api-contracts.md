# API Contracts (v1)

Base path: `/api/v1`

## Auth
- `POST /auth/login`
- `GET /auth/me`

## Sites
- `GET /sites`
- `POST /sites`
- `GET /sites/{site_id}`
- `PUT /sites/{site_id}`

## Projects
- `GET /projects`
- `POST /projects`
- `GET /projects/{project_id}`
- `PUT /projects/{project_id}`
- `POST /projects/{project_id}/stage`

## Project Assignments
- `GET /projects/{project_id}/users`
- `POST /projects/{project_id}/users/assign`
- `DELETE /projects/{project_id}/users/{assignment_id}`

## Design Files
- `POST /projects/{project_id}/design-files`
- `GET /projects/{project_id}/design-files`
- `GET /design-files/{file_id}`
- `POST /design-files/{file_id}/parse`

## Parsed Design Entities
- `GET /projects/{project_id}/sections`
- `GET /projects/{project_id}/inverters`
- `GET /projects/{project_id}/strings`
- `GET /projects/{project_id}/cable-paths`

## Validation Rules (manager only)
- `GET /validation-rules`
- `POST /validation-rules`
- `PUT /validation-rules/{rule_id}`
- `POST /validation-rules/{rule_id}/toggle`

## Validation Runs
- `POST /projects/{project_id}/validation-runs`
- `GET /projects/{project_id}/validation-runs`
- `GET /validation-runs/{run_id}/issues`

## Validation Exceptions
- `POST /validation-issues/{issue_id}/exception`
- `POST /validation-exceptions/{exception_id}/approve`

## Work Packages
- `GET /projects/{project_id}/work-packages`
- `POST /projects/{project_id}/work-packages`
- `PUT /work-packages/{work_package_id}`

## Daily Progress
- `POST /projects/{project_id}/daily-progress`
- `GET /projects/{project_id}/daily-progress`
- `GET /projects/{project_id}/progress-summary`

## Inventory
- `GET /projects/{project_id}/inventory/items`
- `POST /projects/{project_id}/inventory/receipts`
- `POST /projects/{project_id}/inventory/issues`
- `POST /projects/{project_id}/inventory/returns`
- `GET /projects/{project_id}/inventory/transactions`

## Tests & Commissioning
- `GET /projects/{project_id}/tests`
- `POST /projects/{project_id}/tests`
- `PUT /tests/{test_id}`
- `POST /projects/{project_id}/commissioning/check`
- `GET /projects/{project_id}/commissioning/summary`

## Maintenance
- `GET /projects/{project_id}/maintenance/plans`
- `POST /projects/{project_id}/maintenance/plans`
- `POST /projects/{project_id}/maintenance/events`
- `GET /projects/{project_id}/maintenance/events`
