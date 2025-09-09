'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import RenderWorkflow from '@/app/workflow/[workflowId]/RenderWorkflow';
import { getWorkflowApiV1WorkflowFetchWorkflowIdGet } from '@/client/sdk.gen';
import type { WorkflowResponse } from '@/client/types.gen';
import { FlowEdge, FlowNode } from '@/components/flow/types';
import SpinLoader from '@/components/SpinLoader';
import { useAuth } from '@/lib/auth';
import logger from '@/lib/logger';
import { DEFAULT_WORKFLOW_CONFIGURATIONS,WorkflowConfigurations } from '@/types/workflow-configurations';

import WorkflowLayout from '../WorkflowLayout';

export default function WorkflowDetailPage() {
    const params = useParams();
    const [workflow, setWorkflow] = useState<WorkflowResponse | undefined>(undefined);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const { user, getAccessToken, redirectToLogin, loading: authLoading } = useAuth();

    // Redirect if not authenticated
    useEffect(() => {
        if (!authLoading && !user) {
            redirectToLogin();
        }
    }, [authLoading, user, redirectToLogin]);

    useEffect(() => {
        const fetchWorkflow = async () => {
            if (!user) return;
            try {
                const accessToken = await getAccessToken();
                const response = await getWorkflowApiV1WorkflowFetchWorkflowIdGet({
                    path: {
                        workflow_id: Number(params.workflowId)
                    },
                    headers: {
                        'Authorization': `Bearer ${accessToken}`,
                    },
                });
                const workflow = response.data;
                setWorkflow(workflow);
            } catch (err) {
                setError('Failed to fetch workflow');
                logger.error(`Error fetching workflow: ${err}`);
            } finally {
                setLoading(false);
            }
        };

        if (user) {
            fetchWorkflow();
        }
    }, [params.workflowId, user, getAccessToken]);

    if (loading) {
        return (
            <WorkflowLayout>
                <SpinLoader />
            </WorkflowLayout>
        );
    }
    else if (error || !workflow) {
        return (
            <WorkflowLayout showFeaturesNav={false}>
                <div className="flex items-center justify-center min-h-screen">
                    <div className="text-lg text-red-500">{error || 'Workflow not found'}</div>
                </div>
            </WorkflowLayout>
        );
    }
    else {
        return (
            // We are sending custom header actions to WorkflowLayout from RenderWorkflow component
            <RenderWorkflow
                initialWorkflowName={workflow.name}
                workflowId={workflow.id}
                initialFlow={{
                    nodes: workflow.workflow_definition.nodes as FlowNode[],
                    edges: workflow.workflow_definition.edges as FlowEdge[],
                    viewport: { x: 0, y: 0, zoom: 1 }
                }}
                initialTemplateContextVariables={workflow.template_context_variables as Record<string, string> || {}}
                initialWorkflowConfigurations={(workflow.workflow_configurations as WorkflowConfigurations) || DEFAULT_WORKFLOW_CONFIGURATIONS}
            />
        );
    }
}
