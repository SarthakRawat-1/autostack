'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';
import { useProject, useContinueWorkflow } from '@/hooks/useProjects';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    ArrowLeft, CheckCircle2, XCircle, AlertCircle, MessageSquare,
    Code, FileText, TestTube, BookOpen, GitPullRequest, ExternalLink
} from 'lucide-react';
import { cn } from '@/lib/utils';

const PHASE_CONFIG: Record<string, { icon: React.ComponentType<any>; title: string; description: string }> = {
    planning: {
        icon: FileText,
        title: 'PROJECT PLAN REVIEW',
        description: 'Review the generated plan, goals, and task breakdown before development begins'
    },
    developing: {
        icon: Code,
        title: 'CODE REVIEW',
        description: 'Review the generated code and pull request before testing'
    },
    testing: {
        icon: TestTube,
        title: 'TEST RESULTS REVIEW',
        description: 'Review test results and generated test files before documentation'
    },
    documenting: {
        icon: BookOpen,
        title: 'DOCUMENTATION REVIEW',
        description: 'Review the generated documentation before completion'
    },
    reviewing: {
        icon: GitPullRequest,
        title: 'FINAL REVIEW',
        description: 'Review the final results before completing the project'
    }
};

export default function ProjectReviewPage() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.id as string;
    const { data: project, isLoading } = useProject(projectId);
    const continueWorkflow = useContinueWorkflow(projectId);

    const [feedback, setFeedback] = useState('');
    const [showFeedback, setShowFeedback] = useState(false);

    const handleDecision = (decision: 'approve' | 'request_changes' | 'cancel') => {
        if (decision === 'request_changes' && !showFeedback) {
            setShowFeedback(true);
            return;
        }

        continueWorkflow.mutate(
            { decision, feedback: decision === 'request_changes' ? feedback : undefined },
            {
                onSuccess: () => {
                    if (decision === 'cancel') {
                        router.push(`/projects/${projectId}`);
                    }
                }
            }
        );
    };

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

    if (!project.requires_approval) {
        return (
            <div className="p-6 space-y-6">
                <div className="flex items-center justify-center h-64 text-muted-foreground font-mono flex-col gap-4">
                    <CheckCircle2 className="h-12 w-12 text-success" />
                    <span>NO_PENDING_APPROVAL</span>
                    <Link href={`/projects/${projectId}`}>
                        <Button variant="outline" className="font-mono text-xs">
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            BACK TO PROJECT
                        </Button>
                    </Link>
                </div>
            </div>
        );
    }

    const currentPhase = project.current_phase?.toLowerCase() || 'planning';
    const config = PHASE_CONFIG[currentPhase] || PHASE_CONFIG.planning;
    const Icon = config.icon;

    return (
        <div className="p-6 space-y-6 max-w-4xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border/50 pb-6">
                <div className="flex items-center gap-4">
                    <Link href={`/projects/${projectId}`}>
                        <Button variant="ghost" size="sm" className="font-mono text-xs">
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            BACK
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-xl font-mono font-bold uppercase text-white">{project.name}</h1>
                        <span className="text-xs text-muted-foreground font-mono">ID: {project.id.slice(0, 8)}</span>
                    </div>
                </div>
                <Badge variant="tech" className="text-xs font-mono">
                    AWAITING APPROVAL
                </Badge>
            </div>

            {/* Phase Header */}
            <Card className="border-primary/30 bg-primary/5">
                <CardHeader>
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-primary/10 border border-primary/30">
                            <Icon className="h-6 w-6 text-primary" />
                        </div>
                        <div>
                            <CardTitle className="text-lg font-mono uppercase tracking-widest text-primary">
                                {config.title}
                            </CardTitle>
                            <CardDescription className="mt-1">
                                {config.description}
                            </CardDescription>
                        </div>
                    </div>
                </CardHeader>
            </Card>

            {/* Agent Output Area */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-sm font-mono uppercase text-muted-foreground">
                        {currentPhase === 'planning' && 'Generated Plan'}
                        {currentPhase === 'developing' && 'Generated Code'}
                        {currentPhase === 'testing' && 'Test Results'}
                        {currentPhase === 'documenting' && 'Generated Documentation'}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {/* Links Section */}
                    {project.repository_url && (
                        <div className="flex gap-3 mb-4">
                            <Link href={project.repository_url} target="_blank">
                                <Button variant="outline" size="sm" className="font-mono text-xs">
                                    <ExternalLink className="mr-2 h-3 w-3" />
                                    VIEW REPO
                                </Button>
                            </Link>
                            {currentPhase === 'developing' && (
                                <Link href={`${project.repository_url}/pulls`} target="_blank">
                                    <Button variant="outline" size="sm" className="font-mono text-xs">
                                        <GitPullRequest className="mr-2 h-3 w-3" />
                                        VIEW PR
                                    </Button>
                                </Link>
                            )}
                        </div>
                    )}

                    {/* Output Preview Placeholder */}
                    <div className="p-6 bg-secondary/30 border border-border/50 min-h-[200px] flex items-center justify-center text-muted-foreground font-mono text-sm">
                        Agent output preview will be displayed here.
                        <br />
                        Check the repository for generated files.
                    </div>
                </CardContent>
            </Card>

            {/* Feedback Section */}
            {showFeedback && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm font-mono uppercase flex items-center gap-2">
                            <MessageSquare className="h-4 w-4 text-primary" />
                            FEEDBACK
                        </CardTitle>
                        <CardDescription>
                            Describe what changes you want the agent to make
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <textarea
                            value={feedback}
                            onChange={(e) => setFeedback(e.target.value)}
                            placeholder="Be specific about what changes you need..."
                            className="w-full h-32 p-4 bg-card border border-border text-sm font-mono resize-none focus:outline-none focus:border-primary"
                        />
                    </CardContent>
                </Card>
            )}

            {/* Action Buttons */}
            <div className="flex gap-4 pt-4 border-t border-border/50">
                <Button
                    variant="default"
                    onClick={() => handleDecision('approve')}
                    disabled={continueWorkflow.isPending}
                    className="flex-1 font-mono text-xs uppercase tracking-widest h-12"
                >
                    <CheckCircle2 className="mr-2 h-5 w-5" />
                    APPROVE & CONTINUE
                </Button>
                <Button
                    variant="outline"
                    onClick={() => handleDecision('request_changes')}
                    disabled={continueWorkflow.isPending || (showFeedback && !feedback.trim())}
                    className="flex-1 font-mono text-xs uppercase tracking-widest h-12"
                >
                    <AlertCircle className="mr-2 h-5 w-5" />
                    {showFeedback ? 'SUBMIT FEEDBACK' : 'REQUEST CHANGES'}
                </Button>
                <Button
                    variant="ghost"
                    onClick={() => handleDecision('cancel')}
                    disabled={continueWorkflow.isPending}
                    className="font-mono text-xs uppercase tracking-widest h-12 text-destructive hover:text-destructive"
                >
                    <XCircle className="mr-2 h-5 w-5" />
                    CANCEL
                </Button>
            </div>
        </div>
    );
}
