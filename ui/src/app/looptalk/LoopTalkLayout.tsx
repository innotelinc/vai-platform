import React, { ReactNode } from 'react'

import BaseHeader from '@/components/header/BaseHeader'

interface LoopTalkLayoutProps {
    children: ReactNode,
    headerActions?: ReactNode,
    backButton?: ReactNode,
}

const LoopTalkLayout: React.FC<LoopTalkLayoutProps> = ({ children, headerActions, backButton }) => {
    return (
        <>
            <BaseHeader headerActions={headerActions} backButton={backButton} />
            {children}
        </>
    )
}

export default LoopTalkLayout
