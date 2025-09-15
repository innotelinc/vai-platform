'use client';

import { ArrowLeft, FileText, Video } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import BrowserCall from '@/app/workflow/[workflowId]/run/[runId]/BrowserCall';
import WorkflowLayout from '@/app/workflow/WorkflowLayout';
import { getWorkflowRunApiV1WorkflowWorkflowIdRunsRunIdGet } from '@/client/sdk.gen';
import { MediaPreviewButtons, MediaPreviewDialog } from '@/components/MediaPreviewDialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/lib/auth';
import { downloadFile } from '@/lib/files';

interface WorkflowRunResponse {
    is_completed: boolean;
    transcript_url: string | null;
    recording_url: string | null;
    initial_context: Record<string, string | number | boolean | object> | null;
    gathered_context: Record<string, string | number | boolean | object> | null;
}


export default function WorkflowRunPage() {
    const params = useParams();
    const [isLoading, setIsLoading] = useState(true);
    const auth = useAuth();
    const [workflowRun, setWorkflowRun] = useState<WorkflowRunResponse | null>(null);
    const [accessToken, setAccessToken] = useState<string | null>(null);

    // Redirect if not authenticated
    useEffect(() => {
        if (!auth.loading && !auth.isAuthenticated) {
            auth.redirectToLogin();
        }
    }, [auth]);

    // Get access token
    useEffect(() => {
        if (auth.isAuthenticated && !auth.loading) {
            auth.getAccessToken().then(setAccessToken);
        }
    }, [auth]);

    const { openAudioModal, openTranscriptModal, dialog } = MediaPreviewDialog({ accessToken });

    useEffect(() => {
        const fetchWorkflowRun = async () => {
            if (!auth.isAuthenticated || auth.loading) return;

            setIsLoading(true);
            const token = await auth.getAccessToken();
            const workflowId = params.workflowId;
            const runId = params.runId;
            const response = await getWorkflowRunApiV1WorkflowWorkflowIdRunsRunIdGet({
                path: {
                    workflow_id: Number(workflowId),
                    run_id: Number(runId),
                },
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });
            setIsLoading(false);
            setWorkflowRun({
                is_completed: response.data?.is_completed ?? false,
                transcript_url: response.data?.transcript_url ?? null,
                recording_url: response.data?.recording_url ?? null,
                initial_context: response.data?.initial_context as Record<string, string> | null ?? null,
                gathered_context: response.data?.gathered_context as Record<string, string> | null ?? null,
            });
        };
        fetchWorkflowRun();
    }, [params.workflowId, params.runId, auth]);

    const backButton = (
        <div className="flex gap-2">
            <Link href={`/workflow/${params.workflowId}`}>
                <Button variant="outline" size="sm" className="flex items-center gap-1">
                    <ArrowLeft className="h-4 w-4" />
                    Workflow
                </Button>
            </Link>
            <Link href={`/workflow/${params.workflowId}/runs`}>
                <Button variant="outline" size="sm" className="flex items-center gap-1">
                    <ArrowLeft className="h-4 w-4" />
                    Workflow Runs
                </Button>
            </Link>
        </div>
    );

    let returnValue = null;

    if (isLoading) {
        returnValue = (
            <div className="min-h-screen flex mt-40 justify-center">
                <div className="w-full max-w-4xl p-6">
                    <Card>
                        <CardHeader>
                            <Skeleton className="h-6 w-48" />
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-3/4" />
                            <Skeleton className="h-4 w-1/2" />
                        </CardContent>
                        <CardFooter className="flex gap-4">
                            <Skeleton className="h-10 w-32" />
                            <Skeleton className="h-10 w-32" />
                        </CardFooter>
                    </Card>
                </div>
            </div>
        );
    }
    else if (workflowRun?.is_completed) {
        returnValue = (
            <div className="min-h-screen flex mt-40 justify-center p-6">
                <div className="w-full max-w-4xl space-y-6">
                    <Card className="border-gray-100">
                        <CardHeader className="flex flex-row items-center justify-between">
                            <CardTitle className="text-2xl">Agent Run Completed</CardTitle>
                            <div className="h-8 w-8 bg-green-100 rounded-full flex items-center justify-center">
                                <svg className="h-5 w-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <p className="text-gray-600 mb-8">Your voice agent run has been completed successfully. You can preview or download the transcript and recording.</p>

                            <div className="flex flex-wrap gap-4">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-gray-600">Preview:</span>
                                    <MediaPreviewButtons
                                        recordingUrl={workflowRun?.recording_url}
                                        transcriptUrl={workflowRun?.transcript_url}
                                        runId={Number(params.runId)}
                                        onOpenAudio={openAudioModal}
                                        onOpenTranscript={openTranscriptModal}
                                    />
                                </div>
                                <div className="flex items-center gap-2 border-l pl-4">
                                    <span className="text-sm text-gray-600">Download:</span>
                                    <Button
                                        onClick={() => downloadFile(workflowRun?.transcript_url, accessToken!)}
                                        disabled={!workflowRun?.transcript_url || !accessToken}
                                        size="sm"
                                        className="gap-2"
                                    >
                                        <FileText className="h-4 w-4" />
                                        Transcript
                                    </Button>
                                    <Button
                                        onClick={() => downloadFile(workflowRun?.recording_url, accessToken!)}
                                        disabled={!workflowRun?.recording_url || !accessToken}
                                        size="sm"
                                        className="gap-2"
                                    >
                                        <Video className="h-4 w-4" />
                                        Recording
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* <div className="grid gap-6 md:grid-cols-2">
                        <ContextDisplay
                            title="Initial Context"
                            context={workflowRun?.initial_context}
                        />
                        <ContextDisplay
                            title="Gathered Context"
                            context={workflowRun?.gathered_context}
                        />
                    </div> */}
                </div>
            </div>
        );
    }
    else {
        returnValue =
            <div className="min-h-screen mt-40">
                <BrowserCall
                    workflowId={Number(params.workflowId)}
                    workflowRunId={Number(params.runId)}
                    accessToken={accessToken}
                    initialContextVariables={
                        workflowRun?.initial_context
                            ? Object.fromEntries(
                                Object.entries(workflowRun.initial_context).map(([key, value]) => [
                                    key,
                                    typeof value === 'object' && value !== null
                                        ? JSON.stringify(value)
                                        : String(value)
                                ])
                            )
                            : null
                    }
                />
            </div>
    }

    return (
        <WorkflowLayout backButton={backButton}>
            {returnValue}
            {dialog}
        </WorkflowLayout>
    );
}
