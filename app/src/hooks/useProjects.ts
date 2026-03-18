import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, Project } from '@/services/api';
import { toast } from 'sonner';

export type { Project };

export function useProjects() {
    return useQuery({
        queryKey: ['projects'],
        queryFn: () => api.listProjects(),
        refetchInterval: 5000,
    });
}

export function useProject(id: string) {
    return useQuery({
        queryKey: ['project', id],
        queryFn: () => api.getProject(id),
        refetchInterval: 3000,
        enabled: !!id,
    });
}

export function useCreateProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: api.createProject,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['projects'] });
            toast.success('Project created successfully');
        },
        onError: (error: Error) => {
            toast.error(`Failed to create project: ${error.message}`);
        },
    });
}

export function useContinueWorkflow(projectId: string) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            decision,
            feedback
        }: {
            decision: 'approve' | 'request_changes' | 'cancel';
            feedback?: string
        }) => api.continueWorkflow(projectId, decision, feedback),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['project', projectId] });
            toast.success('Workflow decision submitted');
        },
        onError: (error: Error) => {
            toast.error(`Workflow action failed: ${error.message}`);
        },
    });
}
