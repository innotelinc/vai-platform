import { BaseEdge, type Edge, EdgeLabelRenderer, type EdgeProps, getSmoothStepPath, useReactFlow } from '@xyflow/react';
import { AlertCircle, Pencil } from 'lucide-react';
import { useCallback, useState } from 'react';

import { useWorkflow } from "@/app/workflow/[workflowId]/contexts/WorkflowContext";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from '@/components/ui/textarea';
import { cn } from "@/lib/utils";

import { FlowEdge, FlowEdgeData, FlowNode } from '../types';
type CustomEdge = Edge<{ value: number }, 'custom'>;


interface EdgeDetailsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    data?: FlowEdgeData;
    onSave: (value: FlowEdgeData) => void;
}

const EdgeDetailsDialog = ({ open, onOpenChange, data, onSave }: EdgeDetailsDialogProps) => {
    const [condition, setCondition] = useState(data?.condition ?? '');
    const [label, setLabel] = useState(data?.label ?? '');

    const handleSave = () => {
        onSave({ condition: condition, label: label });
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Edit Condition</DialogTitle>
                    {data?.invalid && data.validationMessage && (
                        <div className="mt-2 flex items-center gap-2 rounded-md bg-red-50 p-2 text-sm text-red-500 border border-red-200">
                            <AlertCircle className="h-4 w-4" />
                            <span>{data.validationMessage}</span>
                        </div>
                    )}
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label>Condition Label</Label>
                        <Label className="text-xs text-gray-500">
                            Enter a short label which helps identify this pathway in logs
                        </Label>
                        <Input
                            type="text"
                            value={label}
                            maxLength={64}
                            onChange={(e) => setLabel(e.target.value)}
                        />
                        <div className="text-xs text-gray-500">
                            {label.length}/64 characters
                        </div>
                    </div>
                    <div className="grid gap-2">
                        <Label>Condition</Label>
                        <Label className="text-xs text-gray-500">
                            Describe a condition that will be evaluated to determine if this pathway should be taken
                        </Label>
                        <Textarea
                            value={condition}
                            onChange={(e) => setCondition(e.target.value)}
                        />
                    </div>
                </div>
                <DialogFooter>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                        <Button onClick={handleSave}>Save</Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

interface CustomEdgeProps extends EdgeProps {
    data: FlowEdgeData;
}

export default function CustomEdge(props: CustomEdgeProps) {
    const { id, source, target, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props;

    const { getEdges, setEdges } = useReactFlow<FlowNode, FlowEdge>();
    const { saveWorkflow } = useWorkflow();
    const parallel = getEdges().filter(
        (e) =>
            (e.source === source && e.target === target) ||
            (e.source === target && e.target === source)
    );

    // 2) if there are two, sort by id and pick an index
    let offsetX = 0;
    let offsetY = 0;
    if (parallel.length > 1) {
        const sorted = parallel.slice().sort((a, b) => a.id.localeCompare(b.id));
        const idx = sorted.findIndex((e) => e.id === id);

        // first edge (idx 0) moves right & down;
        // second edge (idx 1) moves left & up
        if (idx === 0) {
            offsetX = 100;
            offsetY = 0;
        } else {
            offsetX = 0;
            offsetY = -50;
        }
    }

    // 3) draw the straight path + get label coords
    const [edgePath, labelX, labelY] = getSmoothStepPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    });

    const [open, setOpen] = useState(false);

    const handleSaveEdgeData = useCallback(async (updatedData: FlowEdgeData) => {
        // Update the node data in the ReactFlow nodes state
        setEdges((edges) => {
            const updatedEdges = edges.map((edge) =>
                edge.id === id
                    ? { ...edge, data: updatedData }
                    : edge
            )
            return updatedEdges;
        }
        );
        // Save the workflow after updating edge data with a small delay to ensure state is updated
        setTimeout(async () => {
            await saveWorkflow();
        }, 100);
    }, [id, setEdges, saveWorkflow]);

    return (
        <>
            <BaseEdge
                id={id}
                path={edgePath}
            />
            <EdgeLabelRenderer>
                <div
                    style={{
                        position: 'absolute',
                        pointerEvents: 'all',
                        transformOrigin: 'center',
                        transform: `translate(-50%, -50%) translate(${labelX + offsetX}px, ${labelY + offsetY}px)`,
                    }}
                    className="nodrag nopan"
                >
                    <div className={cn(
                        "flex items-center gap-2 bg-white pl-3 pr-1 py-1 rounded-md border shadow-sm",
                        data?.invalid ? "border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.5)]" : "border-gray-200"
                    )}>
                        <div className="flex flex-col">
                            <span className="text-sm">{data?.label || data?.condition || 'Set Condition'}</span>

                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 p-0"
                            onClick={() => setOpen(true)}
                        >
                            <Pencil className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </EdgeLabelRenderer>
            <EdgeDetailsDialog
                open={open}
                onOpenChange={setOpen}
                data={data}
                onSave={handleSaveEdgeData}
            />
        </>
    );
}
