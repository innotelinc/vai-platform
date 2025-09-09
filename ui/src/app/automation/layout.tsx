import BaseHeader from "@/components/header/BaseHeader"

export default function CampaignsLayout({
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
