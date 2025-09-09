import BaseHeader from "@/components/header/BaseHeader";

export default function APIKeysLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <>
            <BaseHeader/>
            {children}
        </>
    );
}
