'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateProject } from '@/hooks/useProjects';
import { Button } from '@/components/ui/button';
import { Terminal, Cpu, Shield } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

export default function CreateProjectPage() {
    const router = useRouter();
    const createProject = useCreateProject();
    const [formData, setFormData] = useState<{
        name: string;
        description: string;
        execution_mode: 'auto' | 'manual';
        project_type: 'software' | 'infrastructure';
    }>({
        name: '',
        description: '',
        execution_mode: 'auto',
        project_type: 'software',
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const data = await createProject.mutateAsync(formData);
            router.push(`/projects/${data.id}`);
        } catch (error) {
            console.error('Failed to create project:', error);
        }
    };

    return (
        <div className="max-w-[1200px] mx-auto">
            <div className="mb-10 border-b border-white/10 pb-6">
                <h1 className="text-2xl font-mono font-bold tracking-tight text-white mb-2">Create New Project</h1>
                <p className="text-sm text-gray-500 font-light max-w-2xl">
                    Initialize a new autonomous development workspace. Define your requirements and let the agents build it.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-10">
                {/* Project Details Section */}
                <div className="space-y-6">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">Project Details</h2>
                        <p className="text-xs text-muted-foreground">Basic information about your service.</p>
                    </div>

                    <div className="grid gap-6 md:grid-cols-2">
                        <div className="space-y-2">
                            <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">Project Name</label>
                            <input
                                type="text"
                                required
                                className="flex h-12 w-full rounded-md border border-white/10 bg-black/40 px-4 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700"
                                placeholder="e.g., E-commerce API"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">Description & Requirements</label>
                        <textarea
                            required
                            className="flex min-h-[150px] w-full rounded-md border border-white/10 bg-black/40 px-4 py-3 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700 resize-y"
                            placeholder="Describe the application features, tech stack preferences, and any specific requirements..."
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        />
                    </div>
                </div>

                {/* Execution Mode Section */}
                <div className="space-y-6 pt-6 border-t border-white/5">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">Execution Mode</h2>
                        <p className="text-xs text-muted-foreground">Determine how the agents behave.</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div
                            className={cn(
                                "cursor-pointer rounded-lg border p-6 transition-all duration-200",
                                formData.execution_mode === 'auto'
                                    ? "border-primary/50 bg-primary/5 shadow-[0_0_20px_-12px_rgba(99,102,241,0.5)]"
                                    : "border-white/10 bg-black/20 hover:border-white/20 hover:bg-white/5"
                            )}
                            onClick={() => setFormData({ ...formData, execution_mode: 'auto' })}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className={cn("p-2 rounded-md", formData.execution_mode === 'auto' ? "bg-primary/20 text-primary" : "bg-white/5 text-gray-400")}>
                                    <Cpu className="h-5 w-5" />
                                </div>
                                <span className={cn("font-medium", formData.execution_mode === 'auto' ? "text-white" : "text-gray-300")}>Full Auto</span>
                            </div>
                            <p className="text-sm text-gray-500 leading-relaxed pl-[52px]">
                                Agents work autonomously until completion. Best for rapid prototyping and MVPs.
                            </p>
                        </div>

                        <div
                            className={cn(
                                "cursor-pointer rounded-lg border p-6 transition-all duration-200",
                                formData.execution_mode === 'manual'
                                    ? "border-primary/50 bg-primary/5 shadow-[0_0_20px_-12px_rgba(99,102,241,0.5)]"
                                    : "border-white/10 bg-black/20 hover:border-white/20 hover:bg-white/5"
                            )}
                            onClick={() => setFormData({ ...formData, execution_mode: 'manual' })}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className={cn("p-2 rounded-md", formData.execution_mode === 'manual' ? "bg-primary/20 text-primary" : "bg-white/5 text-gray-400")}>
                                    <Shield className="h-5 w-5" />
                                </div>
                                <span className={cn("font-medium", formData.execution_mode === 'manual' ? "text-white" : "text-gray-300")}>Human-in-the-Loop</span>
                            </div>
                            <p className="text-sm text-gray-500 leading-relaxed pl-[52px]">
                                Review and approve each phase. Best for critical applications requiring oversight.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="flex justify-end gap-3 pt-6 border-t border-white/10">
                    <Link href="/">
                        <Button variant="ghost" type="button" className="text-gray-400 hover:text-white">Cancel</Button>
                    </Link>
                    <Button type="submit" variant="render-white" disabled={createProject.isPending} className="px-8">
                        {createProject.isPending ? (
                            <>
                                <Terminal className="mr-2 h-4 w-4 animate-spin" />
                                INITIALIZING...
                            </>
                        ) : (
                            <>
                                <Terminal className="mr-2 h-4 w-4" />
                                CREATE PROJECT
                            </>
                        )}
                    </Button>
                </div>
            </form>
        </div>
    );
}
