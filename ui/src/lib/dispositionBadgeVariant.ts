// Color variants for disposition code
export const getDispositionBadgeVariant = (code: string | undefined): "default" | "secondary" | "destructive" | "outline" | "success" => {
    if (!code) return "outline";

    const upperCode = code.toUpperCase();
    switch (upperCode) {
        case "XFER":
            return "success"; // Green color for transfers
        case "HU":
        case "NIBP":
            return "destructive"; // Red color for hang up and NIBP
        case "VM":
            return "secondary";
        default:
            return "default"; // Default color for all other codes
    }
};
