import BaseHeader from "@/components/header/BaseHeader"

export default function CreateWorkflowLayout({
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
