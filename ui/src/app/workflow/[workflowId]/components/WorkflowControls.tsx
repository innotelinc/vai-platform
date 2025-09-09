import dagre from '@dagrejs/dagre';
import { ReactFlowInstance } from "@xyflow/react";
import { Check, Pencil } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FlowEdge, FlowNode } from "@/components/flow/types";
import { Button } from "@/components/ui/button";
import { WorkflowConfigurations } from "@/types/workflow-configurations";

import { ConfigurationsDialog } from "./ConfigurationsDialog";
import { TemplateContextVariablesDialog } from "./TemplateContextVariablesDialog";

interface WorkflowControlsProps {
    workflowId: number;
    workflowName: string;
    isEditingName: boolean;
    setIsEditingName: (isEditing: boolean) => void;
    handleNameChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    setIsAddNodePanelOpen: (isOpen: boolean) => void;
    saveWorkflow: (updateWorkflowDefinition: boolean) => Promise<void>;
    nodes: FlowNode[];
    edges: FlowEdge[];
    setNodes: (nodes: FlowNode[] | ((nds: FlowNode[]) => FlowNode[])) => void;
    rfInstance: React.RefObject<ReactFlowInstance<FlowNode, FlowEdge> | null>;
    templateContextVariables?: Record<string, string>;
    saveTemplateContextVariables: (variables: Record<string, string>) => Promise<void>;
    workflowConfigurations: WorkflowConfigurations | null;
    saveWorkflowConfigurations: (configurations: WorkflowConfigurations) => Promise<void>;
}

export const layoutNodes = (
    nodes: FlowNode[],
    edges: FlowEdge[],
    rankdir: 'TB' | 'LR',
    rfInstance: React.RefObject<ReactFlowInstance<FlowNode, FlowEdge> | null>,
    saveWorkflow: (updateWorkflowDefinition: boolean) => Promise<void>
) => {
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir, nodesep: 250, ranksep: 250 });
    g.setDefaultEdgeLabel(() => ({}));

    // Sort nodes so startCall nodes come first and endCall nodes come last
    const sortedNodes = [...nodes].sort((a, b) => {
        if (a.type === 'startCall') return -1;
        if (b.type === 'startCall') return 1;
        if (a.type === 'endCall') return 1;
        if (b.type === 'endCall') return -1;
        return 0;
    });

    sortedNodes.forEach((node) => {
        g.setNode(node.id, { width: 180, height: 60 });
    });

    edges.forEach((edge) => {
        g.setEdge(edge.source, edge.target);
    });

    dagre.layout(g);

    const newNodes = sortedNodes.map((node) => {
        const nodeWithPosition = g.node(node.id);
        return {
            ...node,
            position: { x: nodeWithPosition.x, y: nodeWithPosition.y }
        };
    });

    // Fit view to the new layout and save the viewport position
    setTimeout(() => {
        rfInstance.current?.fitView();
        saveWorkflow(true);
    }, 0);

    return newNodes;
};

const WorkflowControls = ({
    workflowId,
    workflowName,
    isEditingName,
    setIsEditingName,
    handleNameChange,
    setIsAddNodePanelOpen,
    saveWorkflow,
    nodes,
    edges,
    setNodes,
    rfInstance,
    templateContextVariables = {},
    saveTemplateContextVariables,
    workflowConfigurations,
    saveWorkflowConfigurations
}: WorkflowControlsProps) => {
    const router = useRouter();
    const [isContextVarsDialogOpen, setIsContextVarsDialogOpen] = useState(false);
    const [isConfigurationsDialogOpen, setIsConfigurationsDialogOpen] = useState(false);

    return (
        <div>
            <div className="mb-2">
                <div className="flex items-center relative bg-white border border-gray-200 rounded-md px-3 py-1 shadow-sm group hover:border-gray-300 transition-colors w-45">
                    {isEditingName ? (
                        <input
                            type="text"
                            value={workflowName}
                            onChange={handleNameChange}
                            className="pr-8 bg-transparent focus:outline-none w-full text-lg"
                            autoFocus
                            onKeyDown={(e) => e.key === 'Enter' && (setIsEditingName(false), saveWorkflow(false))}
                        />
                    ) : (
                        <h1 className="text-lg font-medium pr-8 truncate">{workflowName}</h1>
                    )}
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => {
                            if (isEditingName) {
                                setIsEditingName(false);
                                saveWorkflow(false);
                            } else {
                                setIsEditingName(true);
                            }
                        }}
                        className="h-7 w-7 absolute right-2 top-1/2 transform -translate-y-1/2"
                    >
                        {isEditingName ? (
                            <Check className="h-4 w-4 text-green-500" />
                        ) : (
                            <Pencil className="h-4 w-4 opacity-50 group-hover:opacity-100 transition-opacity" />
                        )}
                    </Button>
                </div>
            </div>
            <div className="flex flex-col gap-2">
                <Button onClick={() => setIsAddNodePanelOpen(true)}>Add New Node</Button>
                <Button onClick={() => setNodes(layoutNodes(nodes, edges, 'TB', rfInstance, saveWorkflow))}>Vertical Layout</Button>
                <Button onClick={() => setNodes(layoutNodes(nodes, edges, 'LR', rfInstance, saveWorkflow))}>Horizontal Layout</Button>
                <Button
                    onClick={() => setIsConfigurationsDialogOpen(true)}
                    className="flex items-center gap-2"
                >
                    Configurations
                </Button>
                <Button
                    onClick={() => setIsContextVarsDialogOpen(true)}
                    className="flex items-center gap-2"
                >
                    Template Context Variables
                </Button>
                <Button
                    onClick={() => router.push(`/workflow/${workflowId}/runs`)}
                    className="flex items-center gap-1"
                >
                    View Run History
                </Button>
            </div>

            <ConfigurationsDialog
                open={isConfigurationsDialogOpen}
                onOpenChange={setIsConfigurationsDialogOpen}
                workflowConfigurations={workflowConfigurations}
                onSave={saveWorkflowConfigurations}
            />

            <TemplateContextVariablesDialog
                open={isContextVarsDialogOpen}
                onOpenChange={setIsContextVarsDialogOpen}
                templateContextVariables={templateContextVariables}
                onSave={saveTemplateContextVariables}
            />
        </div>
    );
};

export default WorkflowControls;
