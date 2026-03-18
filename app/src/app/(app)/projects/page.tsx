'use client';

import { useProjects } from '@/hooks/useProjects';
import { Button } from '@/components/ui/button';
import { Plus, Activity, GitBranch, Clock, ArrowRight, Terminal } from 'lucide-react';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '@/lib/utils';

export default function ProjectsPage() {
    const { data: projects, isLoading } = useProjects();

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-mono font-bold tracking-tight text-white mb-2">Projects</h1>
                    <p className="text-muted-foreground mt-1">
                        View and manage all your autonomous software projects.
                    </p>
                </div>
                <Link href="/projects/new">
                    <Button variant="render-white" className="gap-2 group">
                        <Plus className="h-4 w-4" />
                        NEW PROJECT
                    </Button>
                </Link>
            </div>

            {isLoading ? (
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div key={i} className="h-64 animate-pulse bg-white/5 border border-white/10 rounded-lg" />
                    ))}
                </div>
            ) : projects?.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center border border-dashed border-border/50 rounded-lg bg-card/20">
                    <div className="rounded-full bg-primary/10 p-4 mb-4">
                        <Plus className="h-8 w-8 text-primary" />
                    </div>
                    <h3 className="text-xl font-semibold text-white mb-2">No projects yet</h3>
                    <p className="text-muted-foreground max-w-md mb-6">
                        Start your first autonomous project and watch the agents build it for you.
                    </p>
                    <Link href="/projects/new">
                        <Button variant="render-white">CREATE PROJECT</Button>
                    </Link>
                </div>
            ) : (
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {projects?.map((project) => (
                        <Link key={project.id} href={`/projects/${project.id}`} className="block h-full">
                            <div className="group relative h-full flex flex-col justify-between border border-white/10 bg-black/40 hover:border-primary/50 transition-all duration-300 hover:shadow-[0_0_30px_-10px_rgba(99,102,241,0.3)] overflow-hidden rounded-lg">
                                {/* Grid Background Effect */}
                                <div className="absolute inset-0 bg-grid-pattern opacity-0 group-hover:opacity-5 transition-opacity duration-500 pointer-events-none" />

                                <div className="p-6 relative z-10 flex-1 flex flex-col">
                                    {/* Header */}
                                    <div className="flex items-start justify-between mb-4">
                                        <div className="flex items-center gap-2">
                                            <div className={cn(
                                                "h-2 w-2 rounded-full",
                                                project.status === 'COMPLETED' ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" :
                                                    project.status === 'FAILED' ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]" :
                                                        project.status === 'DEVELOPING' ? "bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)] animate-pulse" :
                                                            "bg-zinc-500"
                                            )} />
                                            <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                                                {project.status}
                                            </span>
                                        </div>
                                        <Terminal className="h-4 w-4 text-white/20 group-hover:text-primary/50 transition-colors" />
                                    </div>

                                    {/* Title & Desc */}
                                    <h3 className="font-mono text-lg font-bold text-white mb-3 uppercase tracking-tight group-hover:text-primary transition-colors">
                                        {project.name}
                                    </h3>
                                    <p className="text-sm text-muted-foreground line-clamp-3 mb-6 flex-1 font-light leading-relaxed">
                                        {project.description}
                                    </p>

                                    {/* Footer Info */}
                                    <div className="flex items-center justify-between text-xs text-zinc-500 mt-auto pt-4 border-t border-white/5 group-hover:border-primary/20 transition-colors">
                                        <div className="flex items-center gap-1.5">
                                            <GitBranch className="h-3 w-3" />
                                            <span className="font-mono">{project.execution_mode === 'auto' ? 'AUTO' : 'MANUAL'}</span>
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                            <Clock className="h-3 w-3" />
                                            <span>{formatDistanceToNow(new Date(project.created_at))} ago</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Bottom Progress Bar */}
                                {project.progress && (
                                    <div className="relative w-full h-[2px] bg-white/5 mt-auto group-hover:h-[3px] transition-all duration-300">
                                        <div
                                            className="h-full bg-primary shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                                            style={{ width: `${project.progress.percentage}%` }}
                                        />
                                    </div>
                                )}
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
