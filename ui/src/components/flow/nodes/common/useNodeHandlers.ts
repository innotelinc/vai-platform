import { useReactFlow } from "@xyflow/react";
import { useCallback, useState } from "react";

import { FlowEdge, FlowNode, FlowNodeData } from "@/components/flow/types";

interface UseNodeHandlersProps {
    id: string;
    additionalData?: Record<string, string | boolean>;
}

export const useNodeHandlers = ({ id, additionalData = {} }: UseNodeHandlersProps) => {
    const [open, setOpen] = useState(false);
    const { setNodes } = useReactFlow<FlowNode, FlowEdge>();

    const handleSaveNodeData = useCallback(
        (updatedData: FlowNodeData) => {
            setNodes((nodes) => {
                const updatedNodes = nodes.map((node) =>
                    node.id === id
                        ? { ...node, data: { ...node.data, ...updatedData, ...additionalData } }
                        : node
                );
                return updatedNodes;
            });
        },
        [id, setNodes, additionalData]
    );

    const handleDeleteNode = useCallback(() => {
        setNodes((nodes) => nodes.filter((node) => node.id !== id));
    }, [id, setNodes]);

    return {
        open,
        setOpen,
        handleSaveNodeData,
        handleDeleteNode,
    };
};
