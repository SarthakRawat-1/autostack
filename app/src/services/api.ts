import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor — attach JWT token
apiClient.interceptors.request.use((config) => {
    if (typeof window !== 'undefined') {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    }
    return config;
});

// Response interceptor for error handling + 401 redirect
apiClient.interceptors.response.use(
    (response) => response.data,
    (error) => {
        if (error.response?.status === 401 && typeof window !== 'undefined') {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        const message = error.response?.data?.detail || error.message;
        return Promise.reject(new Error(message));
    }
);

export interface Project {
    id: string;
    name: string;
    description: string;
    repository_url?: string;
    project_type?: string; // software or infrastructure
    status: string;
    current_phase: string | null;
    current_interrupt?: string | null;
    execution_mode: "auto" | "manual";
    requires_approval: boolean;
    created_at: string;
    updated_at?: string;
    progress?: {
        percentage: number;
        completed_tasks: number;
        total_tasks: number;
        failed_tasks: number;
        pending_tasks: number;
    };
}

export interface BranchInfo {
    name: string;
    is_default: boolean;
}

export interface CreateProjectRequest {
    name: string;
    description: string;
    repository_url?: string;
    source_branch?: string;
    execution_mode: "auto" | "manual";
    project_type: "software" | "infrastructure";
    credentials?: {
        github_token?: string;
        slack_webhook_url?: string;
        discord_webhook_url?: string;
        azure_subscription_id?: string;
        azure_tenant_id?: string;
        azure_client_id?: string;
        azure_client_secret?: string;
    };
}

export const api = {
    // Projects
    createProject: (data: CreateProjectRequest) =>
        apiClient.post<CreateProjectRequest, Project>('/api/v1/projects', data),

    listProjects: () =>
        apiClient.get<any, Project[]>('/api/v1/projects'),

    getProject: (id: string) =>
        apiClient.get<any, Project>(`/api/v1/projects/${id}`),

    fetchBranches: (repoUrl: string) =>
        apiClient.get<any, BranchInfo[]>('/api/v1/projects/github/branches', { params: { repo_url: repoUrl } }),

    // Workflow
    getWorkflowState: (projectId: string) =>
        apiClient.get<any, any>(`/api/v1/projects/${projectId}/workflow`),

    continueWorkflow: (
        projectId: string,
        decision: 'approve' | 'request_changes' | 'cancel' = 'approve',
        feedback?: string
    ) =>
        apiClient.post<any, any>(`/api/v1/projects/${projectId}/workflow/continue`, {
            decision,
            feedback
        }),

    // Tasks
    listTasks: (projectId: string) =>
        apiClient.get<any, { items: any[]; total: number; limit: number; offset: number }>(`/api/v1/projects/${projectId}/tasks`),

    // Logs
    getLogs: (projectId: string) =>
        apiClient.get<any, any[]>(`/api/v1/projects/${projectId}/logs`),

    // Settings
    getSettings: () =>
        apiClient.get<any, any>('/api/v1/settings'),

    updateSettings: (data: Record<string, string | null>) =>
        apiClient.post<any, any>('/api/v1/settings', data),

    resetSettings: () =>
        apiClient.delete<any, any>('/api/v1/settings'),
};
