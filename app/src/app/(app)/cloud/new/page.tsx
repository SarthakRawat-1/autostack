'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateProject } from '@/hooks/useProjects';
import { Button } from '@/components/ui/button';
import { Cloud, Server, Shield, ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

export default function CreateCloudProjectPage() {
    const router = useRouter();
    const createProject = useCreateProject();
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        repository_url: '',
        execution_mode: 'auto' as 'auto' | 'manual',
        project_type: 'infrastructure' as 'infrastructure' | 'software'
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const data = await createProject.mutateAsync(formData);
            router.push(`/projects/${data.id}`);
        } catch (error) {
            console.error('Failed to create cloud project:', error);
        }
    };

    return (
        <div className="max-w-[1200px] mx-auto">
            <div className="mb-10 border-b border-white/10 pb-6 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-mono font-bold tracking-tight text-white mb-2">
                        Provision Cloud Infrastructure
                    </h1>
                    <p className="text-sm text-gray-500 font-light max-w-2xl">
                        Describe your desired Azure cloud architecture. The AI Architect will design it, and DevOps agents will deploy it using Terraform.
                    </p>
                </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-10">
                {/* Project Details Section */}
                <div className="space-y-6">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">Infrastructure Goal</h2>
                        <p className="text-xs text-muted-foreground">Define what you want to build.</p>
                    </div>

                    <div className="grid gap-6 md:grid-cols-2">
                        <div className="space-y-2">
                            <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">Project Name</label>
                            <input
                                type="text"
                                required
                                className="flex h-12 w-full rounded-md border border-white/10 bg-black/40 px-4 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700"
                                placeholder="e.g., prod-aks-cluster"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">GitHub Repository (Optional)</label>
                        <input
                            type="url"
                            className="flex h-12 w-full rounded-md border border-white/10 bg-black/40 px-4 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700"
                            placeholder="https://github.com/username/repo"
                            value={formData.repository_url}
                            onChange={(e) => setFormData({ ...formData, repository_url: e.target.value })}
                        />
                        <p className="text-xs text-gray-600">
                            Link an existing repository to import Terraform state or codebase.
                        </p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">Requirements & Topology</label>
                        <textarea
                            required
                            className="flex min-h-[150px] w-full rounded-md border border-white/10 bg-black/40 px-4 py-3 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700 resize-y"
                            placeholder="e.g., Create a private AKS cluster in eastus with an Azure SQL instance and a Redis Cache. Ensure no public IPs on nodes."
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        />
                        <p className="text-xs text-gray-500 mt-2">
                            Tip: Specifying regions, machine types, and security requirements helps the Architect design a better plan.
                        </p>
                    </div>
                </div>

                {/* Execution Mode Section - Simplified for Cloud */}
                <div className="space-y-6 pt-6 border-t border-white/5">
                    <p className="text-xs text-gray-600 italic">
                        Note: Cloud Provisioning currently runs in fully autonomous mode.
                    </p>
                </div>

                <div className="flex justify-end gap-3 pt-6 border-t border-white/10">
                    <Link href="/">
                        <Button variant="ghost" type="button" className="text-gray-400 hover:text-white">Cancel</Button>
                    </Link>
                    <Button type="submit" variant="render-white" disabled={createProject.isPending} className="px-8">
                        {createProject.isPending ? (
                            <>
                                <Server className="mr-2 h-4 w-4 animate-spin" />
                                PROVISIONING...
                            </>
                        ) : (
                            <>
                                <Cloud className="mr-2 h-4 w-4" />
                                START PROVISIONING
                            </>
                        )}
                    </Button>
                </div>
            </form>
        </div>
    );
}
