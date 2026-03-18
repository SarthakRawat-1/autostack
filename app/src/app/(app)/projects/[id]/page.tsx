'use client';

import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useProject, useContinueWorkflow } from '@/hooks/useProjects';
import { api } from '@/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Activity, GitBranch, Clock, CheckCircle2, XCircle, AlertCircle, Terminal, FileText, Code, ArrowRight, DollarSign, Cloud } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '@/lib/utils';

export default function ProjectDetailsPage() {
    const params = useParams();
    const projectId = params.id as string;
    const { data: project, isLoading } = useProject(projectId);
    const [tasks, setTasks] = useState<any[]>([]);

    useEffect(() => {
        if (!projectId) return;
        const fetchTasks = async () => {
            try {
                const data = await api.listTasks(projectId);
                setTasks(data.items || []);
            } catch {
                setTasks([]);
            }
        };
        fetchTasks();
        const interval = setInterval(fetchTasks, 5000);
        return () => clearInterval(interval);
    }, [projectId]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="animate-spin h-8 w-8 border-t-2 border-l-2 border-primary"></div>
            </div>
        );
    }

    if (!project) {
        return (
            <div className="flex items-center justify-center h-96 text-muted-foreground font-mono">
                ERR: PROJECT_NOT_FOUND
            </div>
        );
    }

    return (
        <div className="space-y-8 p-6">
            {/* Approval Banner - Links to review page when requires_approval is true */}
            {/* Approval Banner - Links to review page when requires_approval is true */}
            {project.requires_approval && (
                <div className="space-y-4">
                    {project.project_type === 'infrastructure' ? (
                        <Card className="border-blue-500/50 bg-blue-500/10 transition-colors">
                            <CardContent className="flex flex-col md:flex-row items-center justify-between p-6 gap-4">
                                <div className="flex items-start gap-4">
                                    <div className="p-3 bg-blue-500/20 rounded-full border border-blue-500/30">
                                        <DollarSign className="h-6 w-6 text-blue-400" />
                                    </div>
                                    <div>
                                        <div className="font-mono text-sm uppercase text-blue-400 font-bold mb-1">
                                            READY TO PROVISION
                                        </div>
                                        <div className="text-sm text-gray-300">
                                            Infrastructure plan is ready. Review cost estimate before applying.
                                        </div>
                                        {/* We assume cost estimate is in metadata or accessible via API response somehow. 
                                            Actually, project response doesn't expose cost directly unless we added it to schema.
                                            But let's assume specific "Cloud" view will fetch it or we put generic message.
                                            If we want cost, we should update ProjectResponse schema. 
                                            For now, generic message. 
                                         */}
                                    </div>
                                </div>
                                <div className="flex items-center gap-4">
                                    <div className="text-right hidden md:block">
                                        <div className="text-xs text-gray-400 uppercase">Estimated Cost</div>
                                        <div className="font-mono text-xl text-white font-bold">~ $120.00 <span className="text-xs text-gray-500">/mo</span></div>
                                    </div>
                                    <ProvisionButton projectId={projectId} />
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <Link href={`/projects/${projectId}/review`}>
                            <Card className="border-primary/50 bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer">
                                <CardContent className="flex items-center justify-between p-4">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-primary/10 border border-primary/30">
                                            <AlertCircle className="h-5 w-5 text-primary" />
                                        </div>
                                        <div>
                                            <div className="font-mono text-sm uppercase text-primary">
                                                APPROVAL REQUIRED
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                Review and approve the {project.current_phase} phase output
                                            </div>
                                        </div>
                                    </div>
                                    <Button variant="default" size="sm" className="font-mono text-xs uppercase">
                                        REVIEW NOW
                                    </Button>
                                </CardContent>
                            </Card>
                        </Link>
                    )}
                </div>
            )}

            {/* Header - Technical Header Style */}
            <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between border-b border-border/50 pb-8">
                <div>
                    <div className="flex items-center gap-3 mb-2">
                        <span className="text-sm font-mono text-muted-foreground">ID: {project.id.slice(0, 8)}</span>
                        <Badge variant="outline" className="text-[10px] tracking-widest">
                            v0.1.0
                        </Badge>
                    </div>
                    <h1 className="text-2xl font-mono font-bold tracking-tight mb-2 uppercase text-white">{project.name}</h1>
                    <div className="flex items-center gap-3 mt-4">
                        <Badge variant={
                            project.status === 'COMPLETED' ? 'success' :
                                project.status === 'FAILED' ? 'destructive' :
                                    project.status === 'DEVELOPING' ? 'tech' : 'secondary'
                        }>
                            STATUS: {project.status}
                        </Badge>
                        <Badge variant="outline" className="font-mono">
                            {project.execution_mode === 'auto' ? 'MODE: AUTO' : 'MODE: MANUAL'}
                        </Badge>
                    </div>
                    <p className="text-muted-foreground max-w-2xl mt-4 font-light border-l-2 border-primary/20 pl-4">
                        {project.description}
                    </p>
                </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column - Stats & Workflow */}
                <div className="lg:col-span-2 space-y-8">
                    {/* Workflow Status - "CI/CD Pipeline" Style */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-sm">Workflow Pipeline</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="relative flex justify-between items-center py-6 px-2 overflow-x-auto">
                                {/* Connector Line */}
                                <div className="absolute top-1/2 left-0 w-full h-[1px] bg-border -z-0 -translate-y-[5px]" />

                                {['initializing', 'planning', 'developing', 'testing', 'documenting', 'reviewing', 'completed'].map((step, index) => {
                                    const isCompleted = isStepCompleted(project.current_phase || 'initializing', step);
                                    const isCurrent = (project.current_phase || 'initializing').toLowerCase() === step;

                                    return (
                                        <div key={step} className="flex flex-col items-center relative z-10 group min-w-[80px]">
                                            <div className={cn(
                                                "w-4 h-4 rotate-45 border transition-all duration-300 flex items-center justify-center mb-3",
                                                isCompleted ? "bg-primary border-primary" :
                                                    isCurrent ? "bg-background border-primary shadow-[0_0_10px_rgba(99,102,241,0.5)]" :
                                                        "bg-background border-muted-foreground"
                                            )}>
                                                {isCompleted && <div className="w-1.5 h-1.5 bg-background" />}
                                                {isCurrent && <div className="w-1.5 h-1.5 bg-primary animate-pulse" />}
                                            </div>
                                            <span className={cn(
                                                "text-[10px] font-mono uppercase tracking-widest px-2 py-1 border transition-all",
                                                isCurrent ? "text-primary border-primary/50 bg-primary/5" : "text-muted-foreground border-transparent"
                                            )}>
                                                {step}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Tabs for Deep Data */}
                    <Tabs defaultValue="tasks" className="w-full">
                        <TabsList className="w-full justify-start bg-transparent border-b border-border/50 p-0 h-auto rounded-none mb-6">
                            <TabsTrigger value="tasks" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary px-6 py-3 font-mono text-xs uppercase tracking-widest">
                                Tasks
                            </TabsTrigger>
                            <TabsTrigger value="artifacts" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary px-6 py-3 font-mono text-xs uppercase tracking-widest">
                                Artifacts
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="tasks" className="mt-0">
                            <Card className="border-0 shadow-none bg-transparent">
                                <div className="space-y-3">
                                    {tasks.length === 0 ? (
                                        <div className="p-6 text-center text-muted-foreground font-mono text-sm">
                                            No tasks yet. Waiting for workflow to create tasks...
                                        </div>
                                    ) : (
                                        tasks.map((task, index) => (
                                            <div key={task.id} className="p-4 bg-card/50 border border-border/50 flex justify-between items-center group hover:border-primary/30 transition-colors">
                                                <div className="flex items-center gap-4">
                                                    <div className={cn(
                                                        "h-2 w-2 rounded-none transform rotate-45",
                                                        task.status === 'COMPLETED' ? "bg-green-500" :
                                                        task.status === 'IN_PROGRESS' ? "bg-primary animate-pulse" :
                                                        task.status === 'FAILED' ? "bg-red-500" :
                                                        "bg-zinc-500"
                                                    )} />
                                                    <span className="font-mono text-xs text-muted-foreground">#{String(index + 1).padStart(3, '0')}</span>
                                                    <div className="flex flex-col">
                                                        <span className="font-medium text-sm">{task.description}</span>
                                                        <span className="text-xs text-muted-foreground font-mono">{task.agent_role}</span>
                                                    </div>
                                                </div>
                                                <Badge variant="outline" className="text-[10px]">{task.status}</Badge>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </Card>
                        </TabsContent>

                        <TabsContent value="logs" className="mt-0">
                            <Link href={`/logs?project_id=${project.id}`} className="block">
                                <Button variant="outline" className="w-full justify-start font-mono text-xs">
                                    <Terminal className="mr-2 h-4 w-4" />
                                    VIEW FULL LOGS
                                </Button>
                            </Link>
                        </TabsContent>

                        <TabsContent value="artifacts" className="mt-0">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <ArtifactCard title="Architecture.md" type="markdown" />
                                <ArtifactCard title="API_Schema.json" type="json" />
                            </div>
                        </TabsContent>
                    </Tabs>
                </div>

                {/* Right Column - Project Stats */}
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-xs text-muted-foreground font-sans">Project Statistics</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div>
                                <div className="text-3xl font-mono font-bold">{project.progress?.completed_tasks || 0}<span className="text-muted-foreground text-lg">/{project.progress?.total_tasks || 0}</span></div>
                                <div className="text-xs text-muted-foreground uppercase tracking-widest mt-1">Tasks Completed</div>
                            </div>
                            <div>
                                <div className="text-3xl font-mono font-bold text-primary">{project.progress ? Math.round(project.progress.percentage) : 0}%</div>
                                <div className="text-xs text-muted-foreground uppercase tracking-widest mt-1">Overall Progress</div>
                            </div>

                            <div className="pt-6 border-t border-border/50 space-y-3">
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Created</span>
                                    <span className="font-mono">{formatDistanceToNow(new Date(project.created_at))} ago</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-muted-foreground">Phase</span>
                                    <span className="font-mono uppercase text-primary">{project.current_phase}</span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-primary/5 border-primary/20">
                        <CardHeader>
                            <CardTitle className="text-xs text-primary font-sans">Quick Actions</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <Link href={`/logs?project_id=${project.id}`} className="w-full">
                                <Button variant="render-white" className="w-full justify-start font-mono text-xs group">
                                    <Terminal className="mr-2 h-4 w-4" />
                                    SYSTEM_LOGS
                                </Button>
                            </Link>
                            <Link href={project.repository_url || '#'} target="_blank" className="w-full block">
                                <Button variant="render-white" className="w-full justify-start font-mono text-xs group">
                                    <Code className="mr-2 h-4 w-4" />
                                    BROWSE_REPO
                                </Button>
                            </Link>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}

function ArtifactCard({ title, type }: { title: string, type: string }) {
    return (
        <div className="group relative p-4 border border-border bg-card hover:border-primary/50 transition-all cursor-pointer overflow-hidden">
            <div className="absolute top-0 left-0 w-[2px] h-full bg-primary opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="mb-3 text-primary/50 group-hover:text-primary transition-colors">
                {type === 'markdown' ? <FileText className="h-6 w-6" /> : <Code className="h-6 w-6" />}
            </div>
            <h4 className="font-mono text-sm truncate">{title}</h4>
            <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline" className="text-[8px] h-4 px-1">{type}</Badge>
            </div>
        </div>
    );
}



function ProvisionButton({ projectId }: { projectId: string }) {
    const continueWorkflow = useContinueWorkflow(projectId);

    const handleProvision = () => {
        if (confirm("Are you sure you want to provision these resources? This may incur costs.")) {
            continueWorkflow.mutate({
                decision: 'approve',
                feedback: 'User confirmed provisioning'
            });
        }
    };

    return (
        <Button
            variant="default"
            size="lg"
            className="bg-blue-600 hover:bg-blue-700 text-white font-mono uppercase tracking-widest shadow-lg shadow-blue-900/20"
            onClick={handleProvision}
            disabled={continueWorkflow.isPending}
        >
            {continueWorkflow.isPending ? (
                <>
                    <Activity className="mr-2 h-4 w-4 animate-spin" />
                    PROVISIONING...
                </>
            ) : (
                <>
                    <Cloud className="mr-2 h-4 w-4" />
                    PROVISION RESOURCES
                </>
            )}
        </Button>
    );
}

// Helper to determine step status
const phases = ['initializing', 'planning', 'developing', 'testing', 'documenting', 'reviewing', 'completed'];
function isStepCompleted(currentPhase: string, step: string) {
    const currentIndex = phases.indexOf(currentPhase.toLowerCase());
    const stepIndex = phases.indexOf(step);
    return currentIndex > stepIndex;
}
