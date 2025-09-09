import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface ApiKeyErrorDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    error: string | null;
    onNavigateToApiKeys: () => void;
}

export const ApiKeyErrorDialog = ({
    open,
    onOpenChange,
    error,
    onNavigateToApiKeys
}: ApiKeyErrorDialogProps) => {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>API Key Error</DialogTitle>
                    <DialogDescription className="text-red-500 whitespace-pre-line">
                        {error}
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button onClick={onNavigateToApiKeys}>
                        Go to API Keys Settings
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
