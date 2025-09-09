import BaseHeader from "@/components/header/BaseHeader"

export default function ReportsLayout({
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
