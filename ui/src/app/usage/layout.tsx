import BaseHeader from "@/components/header/BaseHeader"

export default function UsageLayout({
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
