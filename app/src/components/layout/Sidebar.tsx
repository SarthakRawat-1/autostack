'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
    LayoutDashboard,
    PlusSquare,
    Settings,
    Activity,
    Layers,
    Terminal,
    GitBranch,
    Cloud
} from 'lucide-react';

const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Projects', href: '/projects', icon: Layers },
    { name: 'Create Project', href: '/projects/new', icon: PlusSquare },
    { name: 'Import Project', href: '/projects/import', icon: GitBranch },
    { name: 'Cloud Provisioning', href: '/cloud/new', icon: Cloud },
    { name: 'Activity Logs', href: '/logs', icon: Activity },
    { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="flex h-screen w-64 flex-col border-r border-border bg-card/50 backdrop-blur-xl">
            <div className="flex h-16 items-center border-b border-border px-6">
                <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
                    <Terminal className="h-6 w-6 text-primary" />
                    <span className="bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                        AutoStack
                    </span>
                </div>
            </div>

            <nav className="flex-1 space-y-1 px-3 py-4">
                {navigation.map((item) => {
                    const isActive = pathname === item.href || (
                        item.href !== '/dashboard' &&
                        pathname.startsWith(item.href) &&
                        !(item.href === '/projects' && (pathname.startsWith('/projects/new') || pathname.startsWith('/projects/import')))
                    );
                    return (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={cn(
                                "group flex items-center px-3 py-2.5 text-sm font-medium transition-all duration-200",
                                isActive
                                    ? "bg-primary/10 text-primary border-l-2 border-primary"
                                    : "text-muted-foreground hover:bg-accent hover:text-white border-l-2 border-transparent"
                            )}
                        >
                            <item.icon
                                className={cn(
                                    "mr-3 h-5 w-5 transition-colors",
                                    isActive ? "text-primary" : "text-muted-foreground group-hover:text-white"
                                )}
                            />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>


        </div>
    );
}
