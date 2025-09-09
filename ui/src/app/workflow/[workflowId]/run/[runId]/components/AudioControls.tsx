import { Mic, MicOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface AudioControlsProps {
    audioInputs: MediaDeviceInfo[];
    selectedAudioInput: string;
    setSelectedAudioInput: (deviceId: string) => void;
    isCompleted: boolean;
    connectionActive: boolean;
    permissionError: string | null;
    start: () => Promise<void>;
    stop: () => void;
    isStarting: boolean;
}

export const AudioControls = ({
    audioInputs,
    selectedAudioInput,
    setSelectedAudioInput,
    isCompleted,
    connectionActive,
    permissionError,
    start,
    stop,
    isStarting
}: AudioControlsProps) => {
    // Check if we have valid audio devices (permissions granted)
    const hasValidDevices = audioInputs.length > 0 && audioInputs.some(device => device.deviceId && device.deviceId.trim() !== '');
    const validAudioInputs = audioInputs.filter(device => device.deviceId && device.deviceId.trim() !== '');

    const requestAudioPermissions = async () => {
        try {
            await navigator.mediaDevices.getUserMedia({ audio: true });
            // This will trigger the parent component to refresh the device list
            window.location.reload();
        } catch (error) {
            console.error('Failed to request audio permissions:', error);
        }
    };

    return (
        <>
            <div className="space-y-2">
                <h3 className="text-sm font-medium">Audio Input</h3>

                {!hasValidDevices ? (
                    <div className="space-y-3">
                        <div className="flex items-center space-x-2 text-amber-600 bg-amber-50 p-3 rounded-md border border-amber-200">
                            <MicOff className="h-4 w-4" />
                            <span className="text-sm">Audio permissions are required to start the call</span>
                        </div>
                        <Button
                            onClick={requestAudioPermissions}
                            variant="outline"
                            className="w-full"
                        >
                            <Mic className="h-4 w-4 mr-2" />
                            Grant Audio Permissions
                        </Button>
                    </div>
                ) : (
                    <Select value={selectedAudioInput} onValueChange={setSelectedAudioInput}>
                        <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select audio input" />
                        </SelectTrigger>
                        <SelectContent>
                            {validAudioInputs.map((device, index) => (
                                <SelectItem key={device.deviceId} value={device.deviceId}>
                                    {device.label || `Audio Device #${index + 1}`}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                )}
            </div>

            {isCompleted && (
                <div className="flex items-center space-x-4">
                    <p className="text-red-500">
                        Workflow run completed. Please refresh the page in a while to see the recording and transcript.
                    </p>
                </div>
            )}

            {!isCompleted && hasValidDevices && (
                <div className="flex items-center space-x-4">
                    {!connectionActive ? (
                        <Button onClick={start} disabled={isStarting}>
                            {isStarting ? 'Starting...' : 'Start'}
                        </Button>
                    ) : (
                        <Button onClick={stop} variant="destructive">Stop</Button>
                    )}
                    {permissionError && (
                        <p className="text-red-500">{permissionError}</p>
                    )}
                </div>
            )}
        </>
    );
};
