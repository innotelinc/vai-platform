import BaseHeader from "@/components/header/BaseHeader"

export default function IntegrationsLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <>
            <BaseHeader />
            {children}
        </>
    )
}
