'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useCreateProject } from '@/hooks/useProjects';
import { api, BranchInfo } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Terminal, Cpu, Shield, GitBranch, Loader2, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

export default function ImportProjectPage() {
    const router = useRouter();
    const createProject = useCreateProject();
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        repository_url: '',
        source_branch: '',
        execution_mode: 'manual' as 'auto' | 'manual',
    });

    // Branch selection state
    const [branches, setBranches] = useState<BranchInfo[]>([]);
    const [isFetchingBranches, setIsFetchingBranches] = useState(false);
    const [branchError, setBranchError] = useState<string | null>(null);

    // Debounced branch fetcher
    useEffect(() => {
        const fetchBranches = async () => {
            const url = formData.repository_url;
            if (!url || !url.includes('github.com')) {
                setBranches([]);
                return;
            }

            setIsFetchingBranches(true);
            setBranchError(null);

            try {
                // Parse owner/repo to ensure valid format before calling API
                const cleanUrl = url.replace(/\.git$/, '').replace(/\/$/, '');
                if (!cleanUrl.match(/github\.com[/:]([^/]+\/[^/]+)/)) {
                    setIsFetchingBranches(false);
                    return;
                }

                const data = await api.fetchBranches(url);
                setBranches(data);

                // Set default branch if source_branch not selected yet
                if (!formData.source_branch) {
                    const defaultBranch = data.find(b => b.is_default);
                    if (defaultBranch) {
                        setFormData(prev => ({ ...prev, source_branch: defaultBranch.name }));
                    } else if (data.length > 0) {
                        setFormData(prev => ({ ...prev, source_branch: data[0].name }));
                    }
                }
            } catch (error) {
                console.error("Failed to fetch branches:", error);
                setBranchError("Failed to load branches. Is the repo private? Make sure you have access.");
            } finally {
                setIsFetchingBranches(false);
            }
        };

        const timeoutId = setTimeout(fetchBranches, 1000); // 1s debounce
        return () => clearTimeout(timeoutId);
    }, [formData.repository_url]);

    const extractRepoName = (url: string): string => {
        try {
            const cleanUrl = url.replace(/\.git$/, '').replace(/\/$/, '');
            const parts = cleanUrl.split('/');
            return parts[parts.length - 1] || 'imported-project';
        } catch {
            return 'imported-project';
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const repoName = extractRepoName(formData.repository_url);
            // Use user-provided name, or fallback to repo name
            const finalProjectName = formData.name.trim() !== '' ? formData.name : repoName;

            const data = await createProject.mutateAsync({
                ...formData,
                name: finalProjectName,
                project_type: 'software',
            });
            router.push(`/projects/${data.id}`);
        } catch (error) {
            console.error('Failed to import project:', error);
        }
    };

    return (
        <div className="max-w-[1200px] mx-auto">
            <div className="mb-10 border-b border-white/10 pb-6">
                <h1 className="text-2xl font-mono font-bold tracking-tight text-white mb-2">Import Existing Repository</h1>
                <p className="text-sm text-gray-500 font-light max-w-2xl">
                    Connect an existing GitHub repository and describe what changes you want the agents to make.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-10">
                {/* Repository Section */}
                <div className="space-y-6">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">Repository</h2>
                        <p className="text-xs text-muted-foreground">The GitHub repository you want to modify.</p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">GitHub Repository URL</label>
                        <input
                            type="url"
                            required
                            className="flex h-12 w-full rounded-md border border-white/10 bg-black/40 px-4 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700"
                            placeholder="https://github.com/username/repository"
                            value={formData.repository_url}
                            onChange={(e) => setFormData({ ...formData, repository_url: e.target.value })}
                        />
                        <p className="text-xs text-gray-600">Must be a repository you have write access to.</p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">Project Name (Optional)</label>
                        <input
                            type="text"
                            className="flex h-12 w-full rounded-md border border-white/10 bg-black/40 px-4 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700"
                            placeholder="My Awesome Project"
                            value={formData.name || ''}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        />
                        <p className="text-xs text-gray-600">Leave blank to use the repository name automatically.</p>
                    </div>

                    {/* Branch Selection */}
                    {(branches.length > 0 || isFetchingBranches || branchError) && (
                        <div className="space-y-2 animate-in fade-in slide-in-from-top-4 duration-500">
                            <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">Source Branch</label>
                            <div className="relative">
                                <select
                                    className="flex h-12 w-full rounded-md border border-white/10 bg-black/40 px-4 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors appearance-none"
                                    value={formData.source_branch}
                                    onChange={(e) => setFormData({ ...formData, source_branch: e.target.value })}
                                    disabled={isFetchingBranches}
                                >
                                    {branches.map(branch => (
                                        <option key={branch.name} value={branch.name}>
                                            {branch.name} {branch.is_default ? '(Default)' : ''}
                                        </option>
                                    ))}
                                </select>
                                <div className="absolute right-4 top-3.5 pointer-events-none">
                                    {isFetchingBranches ? (
                                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                    ) : (
                                        <GitBranch className="h-4 w-4 text-gray-500" />
                                    )}
                                </div>
                            </div>
                            {branchError ? (
                                <p className="text-xs text-red-400 flex items-center gap-1">
                                    <AlertCircle className="h-3 w-3" />
                                    {branchError}
                                </p>
                            ) : (
                                <p className="text-xs text-gray-600">Select the branch you want to start from.</p>
                            )}
                        </div>
                    )}

                    <div className="space-y-2">
                        <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider">What changes do you want?</label>
                        <textarea
                            required
                            className="flex min-h-[180px] w-full rounded-md border border-white/10 bg-black/40 px-4 py-3 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700 resize-y"
                            placeholder="Example: Add user authentication using JWT tokens. Create login and signup endpoints. Add middleware to protect routes that require authentication..."
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
                                Agents work autonomously to improve the repo. Best for large refactors or features.
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
                                Review and approve changes. Best for critical updates requiring oversight.
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
                                ANALYZING...
                            </>
                        ) : (
                            <>
                                <GitBranch className="mr-2 h-4 w-4" />
                                IMPORT PROJECT
                            </>
                        )}
                    </Button>
                </div>
            </form>
        </div>
    );
}
