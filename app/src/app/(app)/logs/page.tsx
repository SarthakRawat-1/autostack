'use client';

import { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useProjects } from '@/hooks/useProjects';
import { api } from '@/services/api';
import { Card } from '@/components/ui/card';
import { Terminal, RefreshCw, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

function LogsContent() {
    const { data: projects } = useProjects();
    const searchParams = useSearchParams();
    const urlProjectId = searchParams.get('project_id');

    const [selectedProjectId, setSelectedProjectId] = useState<string>('');
    const [logs, setLogs] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [dropdownRef]);

    useEffect(() => {
        if (projects && projects.length > 0) {
            if (urlProjectId && projects.some(p => p.id === urlProjectId)) {
                setSelectedProjectId(urlProjectId);
            } else if (!selectedProjectId) {
                setSelectedProjectId(projects[0].id);
            }
        }
    }, [projects, urlProjectId]);

    useEffect(() => {
        if (!selectedProjectId) return;

        const fetchLogs = async () => {
            try {
                setIsLoading(true);
                const data = await api.getLogs(selectedProjectId);
                setLogs(data);
            } catch (error) {
                console.error('Failed to fetch logs', error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchLogs();

        let interval: NodeJS.Timeout;
        if (autoRefresh) {
            interval = setInterval(fetchLogs, 5000);
        }

        return () => clearInterval(interval);
    }, [selectedProjectId, autoRefresh]);

    const selectedProjectName = projects?.find(p => p.id === selectedProjectId)?.name || 'Select Project';

    return (
        <div className="space-y-6 h-[calc(100vh-8rem)] flex flex-col">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-mono font-bold tracking-tight text-white mb-2">Activity Logs</h1>
                    <p className="text-muted-foreground">Real-time execution logs from your agents.</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center group" ref={dropdownRef}>
                        <span className="bg-white text-black px-3 py-2 rounded-l-md text-xs font-bold uppercase tracking-wider border border-white h-9 flex items-center select-none z-20">
                            Project:
                        </span>

                        <div className="relative">
                            <button
                                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                                className={cn(
                                    "relative h-9 rounded-r-md border border-l-0 border-white/20 bg-black text-white px-4 min-w-[180px] flex items-center justify-between transition-colors outline-none overflow-hidden z-10",
                                    "group/btn hover:border-transparent",
                                    "before:absolute before:inset-0 before:bg-primary before:translate-x-[-100%] hover:before:translate-x-0 before:transition-transform before:duration-300 before:ease-out before:-z-10"
                                )}
                            >
                                <span className="text-sm font-medium relative z-20">{selectedProjectName}</span>
                                <ChevronDown className={cn("h-4 w-4 ml-2 transition-transform relative z-20", isDropdownOpen ? "rotate-180" : "")} />
                            </button>

                            {isDropdownOpen && (
                                <div className="absolute right-0 top-full mt-1 w-[240px] z-50 rounded-md border border-white/20 bg-[#0a0a0a] shadow-xl animate-in fade-in zoom-in-95 duration-100 overflow-hidden">
                                    <div className="py-1 max-h-[300px] overflow-y-auto custom-scrollbar">
                                        {projects?.map(p => {
                                            const isActive = p.id === selectedProjectId;
                                            return (
                                                <button
                                                    key={p.id}
                                                    onClick={() => {
                                                        setSelectedProjectId(p.id);
                                                        setIsDropdownOpen(false);
                                                    }}
                                                    className={cn(
                                                        "w-full text-left px-3 py-2.5 text-sm font-medium transition-all duration-200 flex items-center justify-between group/item",
                                                        isActive
                                                            ? "bg-primary/10 text-primary border-l-2 border-primary"
                                                            : "text-muted-foreground hover:bg-white/5 hover:text-white border-l-2 border-transparent"
                                                    )}
                                                >
                                                    <span className="truncate">{p.name}</span>
                                                    {isActive && <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={cn(
                            "h-9 border transition-colors",
                            autoRefresh
                                ? "text-green-500 border-green-500/50 bg-green-500/10 hover:bg-green-500/10 hover:text-green-500 hover:border-green-500/50"
                                : "text-muted-foreground hover:text-white"
                        )}
                    >
                        <RefreshCw className={cn("h-3.5 w-3.5 mr-2", autoRefresh ? "animate-spin" : "")} />
                        {autoRefresh ? 'LIVE' : 'PAUSED'}
                    </Button>
                </div>
            </div>

            <Card className="flex-1 bg-[#0a0a0a] border-border/50 shadow-2xl overflow-hidden flex flex-col">
                <div className="flex items-center justify-between px-4 py-2 border-b border-border/50 bg-white/5">
                    <div className="flex items-center gap-2">
                        <Terminal className="h-4 w-4 text-muted-foreground" />
                        <span className="text-xs font-mono text-muted-foreground">terminal_output.log</span>
                    </div>
                    <div className="flex gap-1.5">
                        <div className="h-2.5 w-2.5 rounded-full bg-red-500/20 border border-red-500/50" />
                        <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50" />
                        <div className="h-2.5 w-2.5 rounded-full bg-green-500/20 border border-green-500/50" />
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-2 custom-scrollbar">
                    {logs.length === 0 ? (
                        <div className="text-muted-foreground text-center py-20">No logs available for this project.</div>
                    ) : (
                        logs.map((log) => (
                            <div key={log.id} className="flex gap-3 group hover:bg-white/5 p-1 rounded transition-colors">
                                <span className="text-xs text-muted-foreground min-w-[140px] select-none">
                                    {format(new Date(log.timestamp), 'MMM dd HH:mm:ss.SSS')}
                                </span>
                                <span className={`text-xs font-bold uppercase tracking-wider min-w-[80px] ${log.level === 'ERROR' ? 'text-red-500' :
                                    log.level === 'WARNING' ? 'text-yellow-500' :
                                        log.level === 'INFO' ? 'text-blue-400' :
                                            'text-gray-500'
                                    }`}>
                                    {log.level}
                                </span>
                                <span className="text-xs text-purple-400 min-w-[100px]">
                                    [{log.agent_role || 'SYSTEM'}]
                                </span>
                                <span className="text-gray-300 break-all">
                                    {log.message}
                                </span>
                            </div>
                        ))
                    )}
                </div>
            </Card>
        </div>
    );
}

export default function LogsPage() {
    return (
        <Suspense fallback={<div className="text-muted-foreground text-center py-20">Loading...</div>}>
            <LogsContent />
        </Suspense>
    );
}

