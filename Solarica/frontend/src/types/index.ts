export type RoleCode = "manager" | "project_manager" | "supervisor" | "inventory_keeper";

export interface Project {
  id: number;
  project_code: string;
  project_name: string;
  status: string;
}
