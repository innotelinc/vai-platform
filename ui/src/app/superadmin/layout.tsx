import BaseHeader from "@/components/header/BaseHeader"

export default function SuperAdminLayout({
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
