import BaseHeader from "@/components/header/BaseHeader"

export default function ServiceConfigurationLayout({
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
