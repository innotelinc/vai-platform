import { useRouter } from "next/navigation";

import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

import {
    ApiKeyErrorDialog,
    AudioControls,
    ConnectionStatus,
    ContextVariablesSection,
    WorkflowConfigErrorDialog
} from "./components";
import { useWebRTC } from "./hooks";

const Pipecat = ({ workflowId, workflowRunId, accessToken, initialContextVariables }: {
    workflowId: number,
    workflowRunId: number,
    accessToken: string | null,
    initialContextVariables?: Record<string, string> | null
}) => {
    const router = useRouter();

    const {
        audioRef,
        audioInputs,
        selectedAudioInput,
        setSelectedAudioInput,
        connectionActive,
        permissionError,
        isCompleted,
        apiKeyModalOpen,
        setApiKeyModalOpen,
        apiKeyError,
        workflowConfigError,
        workflowConfigModalOpen,
        setWorkflowConfigModalOpen,
        iceGatheringState,
        iceConnectionState,
        start,
        stop,
        isStarting,
        initialContext,
        setInitialContext
    } = useWebRTC({ workflowId, workflowRunId, accessToken, initialContextVariables });

    const navigateToApiKeys = () => {
        router.push('/api-keys');
    };

    const navigateToWorkflow = () => {
        router.push(`/workflow/${workflowId}`)
    }

    return (
        <>
            <Card className="w-full max-w-4xl mx-auto">
                <CardHeader>
                    <CardTitle>Workflow Run</CardTitle>
                </CardHeader>

                <CardContent className="space-y-4">
                    <div className="grid gap-4">
                        <>
                            <ContextVariablesSection
                                initialContext={initialContext}
                                setInitialContext={setInitialContext}
                                disabled={connectionActive || isCompleted}
                            />

                            <AudioControls
                                audioInputs={audioInputs}
                                selectedAudioInput={selectedAudioInput}
                                setSelectedAudioInput={setSelectedAudioInput}
                                isCompleted={isCompleted}
                                connectionActive={connectionActive}
                                permissionError={permissionError}
                                start={start}
                                stop={stop}
                                isStarting={isStarting}
                            />

                            <ConnectionStatus
                                iceGatheringState={iceGatheringState}
                                iceConnectionState={iceConnectionState}
                            />
                        </>
                    </div>
                </CardContent>

                <CardFooter className="flex justify-between">
                    <p className="text-xs text-muted-foreground">
                        WebRTC connection status: {connectionActive ? 'Active' : 'Inactive'}
                    </p>
                    <audio ref={audioRef} autoPlay playsInline className="hidden" />
                </CardFooter>
            </Card>

            <ApiKeyErrorDialog
                open={apiKeyModalOpen}
                onOpenChange={setApiKeyModalOpen}
                error={apiKeyError}
                onNavigateToApiKeys={navigateToApiKeys}
            />

            <WorkflowConfigErrorDialog
                open={workflowConfigModalOpen}
                onOpenChange={setWorkflowConfigModalOpen}
                error={workflowConfigError}
                onNavigateToWorkflow={navigateToWorkflow}
            />
        </>
    );
};

export default Pipecat;
