export interface UserProfile {
  id: string;
  user_id: string;
  organization_id: string;
  full_name: string | null;
  phone: string | null;
  position: string | null;
  date_of_birth: string | null;
  hire_date: string | null;
  department_id: string | null;
  sales_group_id: string | null;
  manager_id: string | null;
  timezone: string;
  location: string | null;
  bio: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileFormData {
  full_name?: string;
  phone?: string;
  position?: string;
  date_of_birth?: string | null;
  timezone?: string;
  location?: string;
  bio?: string;
}
