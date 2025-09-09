import React, { ReactNode } from 'react'

import BaseHeader from '@/components/header/BaseHeader'

interface WorkflowLayoutProps {
    children: ReactNode,
    headerActions?: ReactNode,
    backButton?: ReactNode,
    showFeaturesNav?: boolean
}

const WorkflowLayout: React.FC<WorkflowLayoutProps> = ({ children, headerActions, backButton, showFeaturesNav = true }) => {
    return (
        <>
            <BaseHeader headerActions={headerActions} backButton={backButton} showFeaturesNav={showFeaturesNav} />
            {children}
        </>
    )
}

export default WorkflowLayout
