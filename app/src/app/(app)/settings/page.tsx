'use client';

import { useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Save, Key, Webhook, Shield, Check, AlertCircle, Cloud } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function SettingsPage() {
    const [isSaving, setIsSaving] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [formData, setFormData] = useState({
        groqKey: '',
        openRouterKey: '',
        githubToken: '',
        slackWebhook: '',
        discordWebhook: '',
        azureSubscriptionId: '',
        azureTenantId: '',
        azureClientId: '',
        azureClientSecret: ''
    });

    const handleSave = async () => {
        setIsSaving(true);
        setSaveStatus('idle');

        try {
            await api.updateSettings({
                groq_api_key: formData.groqKey || null,
                openrouter_api_key: formData.openRouterKey || null,
                github_token: formData.githubToken || null,
                slack_webhook_url: formData.slackWebhook || null,
                discord_webhook_url: formData.discordWebhook || null,
                azure_subscription_id: formData.azureSubscriptionId || null,
                azure_tenant_id: formData.azureTenantId || null,
                azure_client_id: formData.azureClientId || null,
                azure_client_secret: formData.azureClientSecret || null
            });

            setSaveStatus('success');
            setFormData({
                groqKey: '',
                openRouterKey: '',
                githubToken: '',
                slackWebhook: '',
                discordWebhook: '',
                azureSubscriptionId: '',
                azureTenantId: '',
                azureClientId: '',
                azureClientSecret: ''
            });
        } catch (error) {
            console.error('Failed to save settings:', error);
            setSaveStatus('error');
        } finally {
            setIsSaving(false);
        }
    };

    const InputField = ({ label, value, onChange, placeholder, type = "text", icon: Icon }: any) => (
        <div className="space-y-2">
            <label className="text-xs font-mono font-medium text-gray-400 uppercase tracking-wider flex items-center gap-2">
                {Icon && <Icon className="h-3 w-3" />}
                {label}
            </label>
            <input
                type={type}
                className="flex h-12 w-full rounded-md border border-white/10 bg-black/40 px-4 py-2 text-sm text-white focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors placeholder:text-gray-700 font-mono"
                placeholder={placeholder}
                value={value}
                onChange={(e) => onChange(e.target.value)}
            />
        </div>
    );

    return (
        <div className="max-w-[1200px] mx-auto">
            <div className="mb-10 border-b border-white/10 pb-6">
                <h1 className="text-2xl font-mono font-bold tracking-tight text-white mb-2">System Configuration</h1>
                <p className="text-sm text-gray-500 font-light max-w-2xl">
                    Configure external service integrations and credentials.
                </p>
            </div>

            <div className="space-y-10">
                {/* LLM Credentials Section */}
                <div className="space-y-6">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">LLM Credentials</h2>
                        <p className="text-xs text-muted-foreground">API keys for the underlying AI models.</p>
                    </div>

                    <div className="grid gap-6 md:grid-cols-2">
                        <InputField
                            label="Groq API Key"
                            icon={Key}
                            type="password"
                            placeholder="gsk_........................"
                            value={formData.groqKey}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, groqKey: val }))}
                        />
                        <InputField
                            label="OpenRouter API Key"
                            icon={Key}
                            type="password"
                            placeholder="sk-or-........................"
                            value={formData.openRouterKey}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, openRouterKey: val }))}
                        />
                    </div>
                </div>

                {/* Version Control Section */}
                <div className="space-y-6 pt-6 border-t border-white/5">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">Version Control</h2>
                        <p className="text-xs text-muted-foreground">Access token for GitHub repository management.</p>
                    </div>

                    <div className="max-w-2xl">
                        <InputField
                            label="GitHub Personal Access Token"
                            icon={Shield}
                            type="password"
                            placeholder="ghp_........................"
                            value={formData.githubToken}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, githubToken: val }))}
                        />
                    </div>
                </div>

                {/* Azure Configuration Section */}
                <div className="space-y-6 pt-6 border-t border-white/5">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">Azure Configuration</h2>
                        <p className="text-xs text-muted-foreground">Credentials for Microsoft Azure infrastructure provisioning.</p>
                    </div>

                    <div className="grid gap-6 md:grid-cols-2">
                        <InputField
                            label="Azure Subscription ID"
                            icon={Cloud}
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                            value={formData.azureSubscriptionId}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, azureSubscriptionId: val }))}
                        />
                        <InputField
                            label="Azure Tenant ID"
                            icon={Cloud}
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                            value={formData.azureTenantId}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, azureTenantId: val }))}
                        />
                        <InputField
                            label="Azure Client ID"
                            icon={Key}
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                            value={formData.azureClientId}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, azureClientId: val }))}
                        />
                        <InputField
                            label="Azure Client Secret"
                            icon={Key}
                            type="password"
                            placeholder="Service principal secret"
                            value={formData.azureClientSecret}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, azureClientSecret: val }))}
                        />
                    </div>
                </div>

                {/* Webhooks Section */}
                <div className="space-y-6 pt-6 border-t border-white/5">
                    <div>
                        <h2 className="text-lg font-medium text-white mb-1">Webhooks</h2>
                        <p className="text-xs text-muted-foreground">Destinations for real-time agent notifications.</p>
                    </div>

                    <div className="grid gap-6 md:grid-cols-2">
                        <InputField
                            label="Slack Webhook URL"
                            icon={Webhook}
                            placeholder="https://hooks.slack.com/services/..."
                            value={formData.slackWebhook}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, slackWebhook: val }))}
                        />
                        <InputField
                            label="Discord Webhook URL"
                            icon={Webhook}
                            placeholder="https://discord.com/api/webhooks/..."
                            value={formData.discordWebhook}
                            onChange={(val: string) => setFormData(prev => ({ ...prev, discordWebhook: val }))}
                        />
                    </div>
                </div>

                {/* Save Action */}
                <div className="flex items-center justify-end gap-4 pt-6 border-t border-white/10">
                    {saveStatus === 'success' && (
                        <span className="flex items-center gap-1 text-green-500 text-sm animate-in fade-in slide-in-from-right-5">
                            <Check className="h-4 w-4" />
                            Settings saved successfully!
                        </span>
                    )}
                    {saveStatus === 'error' && (
                        <span className="flex items-center gap-1 text-red-500 text-sm animate-in fade-in slide-in-from-right-5">
                            <AlertCircle className="h-4 w-4" />
                            Failed to save settings
                        </span>
                    )}
                    <Button
                        variant="render-success"
                        className="gap-2 group min-w-[150px]"
                        onClick={handleSave}
                        disabled={isSaving}
                    >
                        <Save className={`h-4 w-4 ${isSaving ? 'animate-spin' : ''}`} />
                        {isSaving ? 'SAVING...' : 'SAVE CHANGES'}
                    </Button>
                </div>
            </div>
        </div>
    );
}
