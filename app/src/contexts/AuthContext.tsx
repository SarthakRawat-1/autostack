'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { apiClient } from '@/services/api';

interface User {
    id: string;
    email: string;
    name: string;
    created_at: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, name: string, password: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const fetchUser = useCallback(async (accessToken: string) => {
        try {
            const res = await apiClient.get('/api/v1/auth/me', {
                headers: { Authorization: `Bearer ${accessToken}` },
            });
            setUser(res as any);
        } catch {
            localStorage.removeItem('token');
            setToken(null);
            setUser(null);
        }
    }, []);

    useEffect(() => {
        const saved = localStorage.getItem('token');
        if (saved) {
            setToken(saved);
            fetchUser(saved).finally(() => setIsLoading(false));
        } else {
            setIsLoading(false);
        }
    }, [fetchUser]);

    const login = async (email: string, password: string) => {
        const res: any = await apiClient.post('/api/v1/auth/login', { email, password });
        const accessToken = res.access_token;
        localStorage.setItem('token', accessToken);
        setToken(accessToken);
        await fetchUser(accessToken);
    };

    const register = async (email: string, name: string, password: string) => {
        const res: any = await apiClient.post('/api/v1/auth/register', { email, name, password });
        const accessToken = res.access_token;
        localStorage.setItem('token', accessToken);
        setToken(accessToken);
        await fetchUser(accessToken);
    };

    const logout = () => {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
