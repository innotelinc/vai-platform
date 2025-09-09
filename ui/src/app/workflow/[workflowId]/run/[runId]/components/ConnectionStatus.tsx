interface ConnectionStatusProps {
    iceGatheringState: string;
    iceConnectionState: string;
}

export const ConnectionStatus = ({
    iceGatheringState,
    iceConnectionState
}: ConnectionStatusProps) => {
    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
                <h3 className="text-sm font-medium">ICE gathering state</h3>
                <p className="text-sm text-muted-foreground">{iceGatheringState}</p>
            </div>
            <div className="space-y-2">
                <h3 className="text-sm font-medium">ICE connection state</h3>
                <p className="text-sm text-muted-foreground">{iceConnectionState}</p>
            </div>
        </div>
    );
};
