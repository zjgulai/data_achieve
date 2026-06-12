export type AuthSession = {
  user: {
    id: string;
    email: string;
    name: string;
    status: string;
  };
  workspace: {
    id: string;
    name: string;
    slug: string;
    ownerId: string;
  };
};

export type ProjectDomain = "osint" | "ecommerce" | "social" | "competitor" | "mixed";
export type ProjectStatus = "active" | "archived";

export type Project = {
  id: string;
  name: string;
  description: string | null;
  domain: ProjectDomain;
  status: ProjectStatus;
  intelligenceCount: number;
  sourceCount: number;
};

export type ProjectCreateInput = {
  name: string;
  description?: string;
  domain: ProjectDomain;
};
