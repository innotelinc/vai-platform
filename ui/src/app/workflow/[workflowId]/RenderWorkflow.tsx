import '@xyflow/react/dist/style.css';

import {
    Background,
    Panel,
    ReactFlow,
} from "@xyflow/react";
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';

import WorkflowLayout from '@/app/workflow/WorkflowLayout';
import { FlowEdge, FlowNode, NodeType } from "@/components/flow/types";
import { Button } from '@/components/ui/button';
import { WorkflowConfigurations } from '@/types/workflow-configurations';

import AddNodePanel from "../../../components/flow/AddNodePanel";
import CustomEdge from "../../../components/flow/edges/CustomEdge";
import { AgentNode, EndCall, GlobalNode, StartCall } from "../../../components/flow/nodes";
import WorkflowControls from "./components/WorkflowControls";
import WorkflowHeader from "./components/WorkflowHeader";
import { WorkflowProvider } from "./contexts/WorkflowContext";
import { useWorkflowState } from "./hooks/useWorkflowState";

// Define the node types dynamically based on the onSave prop
const nodeTypes = {
    [NodeType.START_CALL]: StartCall,
    [NodeType.AGENT_NODE]: AgentNode,
    [NodeType.END_CALL]: EndCall,
    [NodeType.GLOBAL_NODE]: GlobalNode,
};

const edgeTypes = {
    custom: CustomEdge,
};

interface RenderWorkflowProps {
    initialWorkflowName: string;
    workflowId: number;
    initialFlow?: {
        nodes: FlowNode[];
        edges: FlowEdge[];
        viewport: {
            x: number;
            y: number;
            zoom: number;
        };
    };
    initialTemplateContextVariables?: Record<string, string>;
    initialWorkflowConfigurations?: WorkflowConfigurations;
}

function RenderWorkflow({ initialWorkflowName, workflowId, initialFlow, initialTemplateContextVariables, initialWorkflowConfigurations }: RenderWorkflowProps) {
    const {
        rfInstance,
        nodes,
        edges,
        isAddNodePanelOpen,
        workflowName,
        isEditingName,
        isDirty,
        workflowValidationErrors,
        templateContextVariables,
        workflowConfigurations,
        setNodes,
        setIsAddNodePanelOpen,
        setIsEditingName,
        handleNodeSelect,
        handleNameChange,
        saveWorkflow,
        onConnect,
        onEdgesChange,
        onNodesChange,
        onRun,
        saveTemplateContextVariables,
        saveWorkflowConfigurations
    } = useWorkflowState({ initialWorkflowName, workflowId, initialFlow, initialTemplateContextVariables, initialWorkflowConfigurations });

    const backButton = (
        <Link href="/workflow">
            <Button variant="outline" size="sm" className="flex items-center gap-1">
                <ArrowLeft className="h-4 w-4" />
                Workflows
            </Button>
        </Link>
    );

    const headerActions = (
        <WorkflowHeader
            workflowValidationErrors={workflowValidationErrors}
            isDirty={isDirty}
            workflowName={workflowName}
            rfInstance={rfInstance}
            onRun={onRun}
            workflowId={workflowId}
            saveWorkflow={saveWorkflow}
        />
    );

    return (
        <WorkflowProvider value={{ saveWorkflow }}>
            <WorkflowLayout headerActions={headerActions} backButton={backButton} showFeaturesNav={false}>
                <div className="h-[calc(100vh-80px)]">
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        nodeTypes={nodeTypes}
                        edgeTypes={edgeTypes}
                        onConnect={onConnect}
                        onInit={(instance) => {
                            rfInstance.current = instance;
                        }}
                        defaultEdgeOptions={{ animated: true, type: "custom" }}
                    >
                        <Background />
                        <Panel position="top-left">
                            <WorkflowControls
                                workflowId={workflowId}
                                workflowName={workflowName}
                                isEditingName={isEditingName}
                                setIsEditingName={setIsEditingName}
                                handleNameChange={handleNameChange}
                                setIsAddNodePanelOpen={setIsAddNodePanelOpen}
                                saveWorkflow={saveWorkflow}
                                nodes={nodes}
                                edges={edges}
                                setNodes={setNodes}
                                rfInstance={rfInstance}
                                templateContextVariables={templateContextVariables}
                                saveTemplateContextVariables={saveTemplateContextVariables}
                                workflowConfigurations={workflowConfigurations}
                                saveWorkflowConfigurations={saveWorkflowConfigurations}
                            />
                        </Panel>
                    </ReactFlow>
                </div>

                <AddNodePanel
                    isOpen={isAddNodePanelOpen}
                    onNodeSelect={handleNodeSelect}
                    onClose={() => setIsAddNodePanelOpen(false)}
                />
            </WorkflowLayout>
        </WorkflowProvider>
    );
}

export default RenderWorkflow;
