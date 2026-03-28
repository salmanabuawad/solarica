insert into roles(role_code, role_name, scope_type) values
('manager', 'Manager', 'global'),
('project_manager', 'Project Manager', 'project'),
('supervisor', 'Supervisor', 'project'),
('inventory_keeper', 'Inventory Keeper', 'project')
on conflict (role_code) do nothing;
