import BaseHeader from "@/components/header/BaseHeader"

export default function StackLayout({
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
