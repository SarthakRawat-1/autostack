'use client';

import { Search, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';

export function Header() {
    const { user, logout } = useAuth();

    return (
        <header className="sticky top-0 z-50 flex h-16 w-full items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur-xl">
            <div className="flex items-center gap-4">
                <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Search projects..."
                        className="h-9 w-64 bg-secondary/50 pl-9 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all hover:bg-secondary/80"
                    />
                </div>
            </div>

            <div className="flex items-center gap-4">
                {user && (
                    <span className="text-sm text-muted-foreground font-mono">
                        {user.name}
                    </span>
                )}
                <Button variant="ghost" size="icon" className="text-red-500 hover:text-red-400" onClick={logout} title="Sign out">
                    <LogOut className="h-5 w-5" />
                </Button>
            </div>
        </header>
    );
}
