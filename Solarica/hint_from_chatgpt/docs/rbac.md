# RBAC

## Roles

### Global role
- `manager`

### Project-scoped roles
- `project_manager`
- `supervisor`
- `inventory_keeper`

## Permission matrix

| Action | manager | project_manager | supervisor | inventory_keeper |
|---|---:|---:|---:|---:|
| Create site/project | Y | N | N | N |
| Assign users to project | Y | N | N | N |
| Upload design file | Y | Y | N | N |
| Run validation | Y | Y | View | N |
| Approve validation exception | Y | Y (project only) | N | N |
| Create work package | Y | Y | N | N |
| Submit daily progress | Optional | Y | Y | N |
| Manage project inventory | Y | View | N | Y |
| Record tests | Y | Y | Y | N |
| Approve commissioning | Y | Y | N | N |
| Manage global rules | Y | N | N | N |

## Enforcement model

- JWT for session auth
- DB-backed role checks for every mutating route
- Helpers:
  - `require_global_role("manager")`
  - `require_project_role(project_id, [...])`

## Optional future enhancements

- section-level assignments
- temporary delegated permissions
- audit trails for approvals
