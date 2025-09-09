import { createContext, useContext } from 'react';

interface WorkflowContextType {
    saveWorkflow: (updateWorkflowDefinition?: boolean) => Promise<void>;
}

const WorkflowContext = createContext<WorkflowContextType | undefined>(undefined);

export const WorkflowProvider = WorkflowContext.Provider;

export const useWorkflow = () => {
    const context = useContext(WorkflowContext);
    if (!context) {
        throw new Error('useWorkflow must be used within a WorkflowProvider');
    }
    return context;
};
