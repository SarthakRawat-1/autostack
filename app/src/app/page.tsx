'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Terminal, ArrowRight, Cpu, Shield, GitBranch, Play, Cloud, Search, Bell, Brain, Lock, FileCode } from 'lucide-react';
import { motion } from 'framer-motion';

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen bg-[#050505] text-white overflow-hidden selection:bg-primary/30">
      {/* Background Gradients */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/5 blur-[120px] rounded-full opacity-30" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-600/5 blur-[120px] rounded-full opacity-30" />
        <div className="absolute inset-0 bg-grid-pattern opacity-[0.03]" />
      </div>

      {/* Navbar */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
          <Terminal className="h-6 w-6 text-primary" />
          <span className="font-mono tracking-tighter">
            AUTOSTACK
          </span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/login">
            <Button variant="render-purple" className="text-gray-400 hover:text-white group">Sign In</Button>
          </Link>
          <Link href="/register">
            <Button variant="render" size="sm" className="group">
              Sign Up
            </Button>
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center text-center px-4 py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="max-w-4xl mx-auto space-y-8"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-white/5 border border-white/10 text-xs font-mono text-primary/80 mb-4 tech-border">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
            SYSTEM ONLINE: v1.0.0
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight leading-tight uppercase font-mono">
            Build Software with <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-indigo-400 to-white animate-gradient">
              Autonomous Agents
            </span>
          </h1>

          <p className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed font-light">
            AutoStack orchestrates a team of specialized AI agents to plan, code, test, and document your applications.
            From concept to deployment, completely autonomous.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-6 pt-8">
            <Link href="/login">
              <Button size="lg" variant="render" className="text-lg group">
                Start Building
                <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </Button>
            </Link>
            <Link href="https://www.youtube.com/watch?v=dQw4w9WgXcQ" target="_blank" rel="noopener noreferrer">
              <Button size="lg" variant="render-red" className="text-lg group">
                <Play className="mr-2 h-4 w-4 fill-current group-hover:text-white transition-colors" />
                View Demo
              </Button>
            </Link>
          </div>
        </motion.div>

        {/* Feature Grid */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
          className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto mt-32 w-full"
        >
          <FeatureCard
            icon={<Cpu className="h-6 w-6 text-primary" />}
            title="Multi-Agent System"
            description="PM, Developer, QA, and Documentation agents collaborate in a self-healing pipeline — QA automatically requests fixes until tests pass."
          />
          <FeatureCard
            icon={<GitBranch className="h-6 w-6 text-blue-400" />}
            title="GitHub Integration"
            description="Agents create repositories, manage branches, commit code, and open pull requests — full Git workflow, zero manual steps."
          />
          <FeatureCard
            icon={<Shield className="h-6 w-6 text-indigo-400" />}
            title="Human-in-the-Loop"
            description="Run fully autonomous or pause before each phase for manual review. Provide feedback to loop agents back to any earlier stage."
          />
          <FeatureCard
            icon={<Cloud className="h-6 w-6 text-sky-400" />}
            title="Cloud Infrastructure"
            description="A 3-agent triad (Architect, DevOps, SecOps) designs, generates Terraform, validates security with Checkov, and estimates Azure costs with Infracost."
          />
          <FeatureCard
            icon={<Search className="h-6 w-6 text-yellow-400" />}
            title="Real-Time Research"
            description="Tavily AI search keeps agents up to date on current package versions, tech stacks, and best practices before writing a single line of code."
          />
          <FeatureCard
            icon={<Brain className="h-6 w-6 text-pink-400" />}
            title="Semantic Memory"
            description="ChromaDB vector store with Gemini embeddings gives agents persistent memory across tasks — no repeated context, smarter decisions."
          />
          <FeatureCard
            icon={<FileCode className="h-6 w-6 text-emerald-400" />}
            title="RepoMap Analysis"
            description="Tree-sitter powered code analysis generates semantic maps of existing repositories so agents understand your codebase before touching it."
          />
          <FeatureCard
            icon={<Bell className="h-6 w-6 text-orange-400" />}
            title="Live Notifications"
            description="Get real-time Slack and Discord alerts for workflow events — PR creation, phase completions, failures, and infrastructure provisioning updates."
          />
          <FeatureCard
            icon={<Lock className="h-6 w-6 text-red-400" />}
            title="Secure Credentials"
            description="Per-project credentials encrypted with Fernet. Use system-wide keys or supply your own GitHub token, webhooks, and Azure service principal per project."
          />
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 py-8 text-center text-sm text-gray-600 font-mono">
        <p>COPYRIGHT © 2026 AUTOSTACK INC. // ALL SYSTEMS NOMINAL</p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="group p-6 bg-black border border-white/10 hover:border-primary/50 transition-all duration-300 text-left tech-border">
      <div className="mb-4 p-3 bg-white/5 w-fit group-hover:scale-110 transition-transform duration-300">
        {icon}
      </div>
      <h3 className="text-xl font-bold mb-2 text-gray-200 font-mono uppercase">{title}</h3>
      <p className="text-gray-400 leading-relaxed font-light">{description}</p>
    </div>
  );
}
