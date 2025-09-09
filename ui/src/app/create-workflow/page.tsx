'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { createWorkflowFromTemplateApiV1WorkflowCreateTemplatePost } from '@/client/sdk.gen';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAuth } from '@/lib/auth';
import logger from '@/lib/logger';

export default function CreateWorkflowPage() {
    const router = useRouter();
    const { user, getAccessToken } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [callType, setCallType] = useState<'INBOUND' | 'OUTBOUND'>('INBOUND');
    const [useCase, setUseCase] = useState('');
    const [activityDescription, setActivityDescription] = useState('');

    const handleCreateWorkflow = async () => {
        if (!useCase || !activityDescription) {
            setError('Please fill in all fields');
            return;
        }

        if (!user) {
            setError('You must be logged in to create a workflow');
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const accessToken = await getAccessToken();

            // Call the API to create workflow from template
            const response = await createWorkflowFromTemplateApiV1WorkflowCreateTemplatePost({
                body: {
                    call_type: callType,
                    use_case: useCase,
                    activity_description: activityDescription,
                },
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            });

            if (response.data?.id) {
                router.push(`/workflow/${response.data.id}`);
            }
        } catch (err) {
            setError('Failed to create workflow. Please try again.');
            logger.error(`Error creating workflow: ${err}`);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-[calc(100vh-64px)] flex items-center justify-center p-4 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
            <Card className="w-full max-w-4xl shadow-xl border-0 bg-white/95 dark:bg-gray-900/95 backdrop-blur">
                <CardHeader className="text-center pb-4 pt-6">
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                        Create Your Voice Agent Workflow
                    </h1>
                    <CardDescription className="text-base mt-2 text-gray-600 dark:text-gray-400">
                        Tell us about your use case and we&apos;ll create a customized workflow for you
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 px-6 pb-6">
                    <div className="space-y-4">
                        <div className="flex flex-col space-y-4">
                            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                                <div className="flex items-center flex-wrap gap-2">
                                    <span className="text-base font-medium text-gray-700 dark:text-gray-300">I want to create an</span>
                                    <Select value={callType} onValueChange={(value) => setCallType(value as 'INBOUND' | 'OUTBOUND')}>
                                        <SelectTrigger className="w-[180px] h-10 text-sm font-semibold border-2 focus:ring-2 focus:ring-blue-500">
                                            <SelectValue placeholder="Select type" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="INBOUND" className="text-sm">
                                                <span className="font-medium">📞 INBOUND</span>
                                                <span className="text-xs text-gray-500 ml-1">(Users call AI)</span>
                                            </SelectItem>
                                            <SelectItem value="OUTBOUND" className="text-sm">
                                                <span className="font-medium">☎️ OUTBOUND</span>
                                                <span className="text-xs text-gray-500 ml-1">(AI calls users)</span>
                                            </SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <span className="text-base font-medium text-gray-700 dark:text-gray-300">voice agent</span>
                                </div>
                            </div>

                            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2">
                                    Use Case
                                </label>
                                <div className="flex items-start flex-col gap-2">
                                    <span className="text-base font-medium text-gray-700 dark:text-gray-300">Which serves the use case:</span>
                                    <Input
                                        className="w-full h-10 text-sm px-3 border-2 focus:ring-2 focus:ring-blue-500 transition-all"
                                        placeholder="e.g., Lead Qualification, HR Screening, Customer Support"
                                        value={useCase}
                                        onChange={(e) => setUseCase(e.target.value)}
                                    />
                                </div>
                            </div>

                            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-2">
                                    Activity Description
                                </label>
                                <div className="flex items-start flex-col gap-2">
                                    <span className="text-base font-medium text-gray-700 dark:text-gray-300">Which can:</span>
                                    <textarea
                                        className="w-full min-h-[80px] text-sm px-3 py-2 border-2 rounded-md focus:ring-2 focus:ring-blue-500 transition-all resize-none"
                                        placeholder="Describe what your voice agent will do (e.g., Qualify leads for real estate, Screen candidates for roles, Handle customer support)"
                                        value={activityDescription}
                                        onChange={(e) => setActivityDescription(e.target.value)}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    {error && (
                        <div className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 p-3 rounded-lg border border-red-200 dark:border-red-800 flex items-center gap-2">
                            <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                            </svg>
                            {error}
                        </div>
                    )}

                    <div className="pt-2">
                        <Button
                            onClick={handleCreateWorkflow}
                            disabled={isLoading || !useCase || !activityDescription}
                            className="w-full h-12 text-base font-semibold bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 transition-all transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                            size="lg"
                        >
                            {isLoading ? (
                                <span className="flex items-center gap-3">
                                    <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Creating Your Workflow...
                                </span>
                            ) : (
                                <span className="flex items-center gap-2">
                                    Create Workflow
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                    </svg>
                                </span>
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
