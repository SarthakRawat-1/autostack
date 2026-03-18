'use client';

import { useProjects } from '@/hooks/useProjects';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Plus, ArrowRight, Activity, GitBranch, CheckCircle2, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '@/lib/utils';

export function DashboardView() {
    const { data: projects, isLoading } = useProjects();

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-mono font-bold tracking-tight text-white mb-2">Dashboard</h1>
                    <p className="text-muted-foreground mt-1">
                        Manage your autonomous software projects.
                    </p>
                </div>
                <Link href="/projects/new">
                    <Button variant="render-white" className="group">
                        <Plus className="mr-2 h-4 w-4" />
                        NEW PROJECT
                    </Button>
                </Link>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card className="bg-card/50 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Projects</CardTitle>
                        <Activity className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">{projects?.length || 0}</div>
                        <p className="text-xs text-muted-foreground">
                            Active workspaces
                        </p>
                    </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Active Agents</CardTitle>
                        <GitBranch className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">
                            {projects?.filter(p => p.status === 'DEVELOPING').length ? 'Running' : 'Idle'}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            System status
                        </p>
                    </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Completed</CardTitle>
                        <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">
                            {projects?.filter(p => p.status === 'COMPLETED').length || 0}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Successfully shipped
                        </p>
                    </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Failed</CardTitle>
                        <AlertCircle className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">
                            {projects?.filter(p => p.status === 'FAILED').length || 0}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Requires attention
                        </p>
                    </CardContent>
                </Card>
            </div>

            <div className="space-y-4">
                <h2 className="text-xl font-semibold tracking-tight text-white">Recent Projects</h2>

                {isLoading ? (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {[1, 2, 3].map((i) => (
                            <Card key={i} className="h-48 animate-pulse bg-card/30" />
                        ))}
                    </div>
                ) : projects?.length === 0 ? (
                    <Card className="flex flex-col items-center justify-center py-12 text-center border-dashed">
                        <div className="rounded-full bg-primary/10 p-3 mb-4">
                            <PlusSquare className="h-6 w-6 text-primary" />
                        </div>
                        <h3 className="text-lg font-semibold text-white">No projects yet</h3>
                        <p className="text-sm text-muted-foreground max-w-sm mt-1 mb-4">
                            Start your first autonomous project and watch the agents build it for you.
                        </p>
                        <Link href="/projects/new">
                            <Button variant="outline">Create Project</Button>
                        </Link>
                    </Card>
                ) : (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {projects?.map((project) => (
                            <Link key={project.id} href={`/projects/${project.id}`}>
                                <Card className="group relative overflow-hidden transition-all hover:shadow-lg hover:shadow-primary/10 hover:-translate-y-1">
                                    <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
                                    <CardHeader>
                                        <div className="flex items-start justify-between">
                                            <CardTitle className="line-clamp-1 text-lg">{project.name}</CardTitle>
                                            <span className={cn(
                                                "px-2 py-1 rounded text-[10px] font-medium uppercase tracking-wider border",
                                                project.status === 'COMPLETED' ? "bg-green-500/10 text-green-500 border-green-500/20" :
                                                    project.status === 'FAILED' ? "bg-red-500/10 text-red-500 border-red-500/20" :
                                                        project.status === 'DEVELOPING' ? "bg-blue-500/10 text-blue-500 border-blue-500/20 animate-pulse" :
                                                            "bg-zinc-500/10 text-zinc-500 border-zinc-500/20"
                                            )}>
                                                {project.status}
                                            </span>
                                        </div>
                                        <CardDescription className="line-clamp-2 mt-2">
                                            {project.description}
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex items-center justify-between text-xs text-muted-foreground mt-4">
                                            <div className="flex items-center gap-1">
                                                <Activity className="h-3 w-3" />
                                                {project.execution_mode}
                                            </div>
                                            <div className="flex items-center gap-1">
                                                {formatDistanceToNow(new Date(project.created_at), { addSuffix: true })}
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function PlusSquare(props: any) {
    return (
        <svg
            {...props}
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M8 12h8" />
            <path d="M12 8v8" />
        </svg>
    )
}
