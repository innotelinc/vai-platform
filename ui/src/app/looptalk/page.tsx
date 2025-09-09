import { Suspense } from 'react';

import { CreateTestSessionButton } from '@/components/looptalk/CreateTestSessionButton';
import { LoopTalkTestSessionsList } from '@/components/looptalk/LoopTalkTestSessionsList';
import { getServerAuthProvider, isServerAuthenticated } from '@/lib/auth/server';

import LoopTalkLayout from "./LoopTalkLayout";

async function PageContent() {
    const authProvider = getServerAuthProvider();
    const isAuthenticated = await isServerAuthenticated();

    if (authProvider === 'stack' && !isAuthenticated) {
        const { redirect } = await import('next/navigation');
        redirect('/');
    }

    return (
        <div className="container mx-auto px-4 py-8">
            {/* Active Tests Section */}
            <div className="mb-12">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl font-bold">Active Tests</h2>
                </div>
                <LoopTalkTestSessionsList status="active" />
            </div>

            {/* Test Sessions Section */}
            <div className="mb-6">
                <div className="flex justify-between items-center mb-6">
                    <h1 className="text-2xl font-bold">Test Sessions</h1>
                    <CreateTestSessionButton />
                </div>
                <LoopTalkTestSessionsList />
            </div>
        </div>
    );
}

function LoopTalkLoading() {
    return (
        <div className="container mx-auto px-4 py-8">
            {/* Active Tests Section Loading */}
            <div className="mb-12">
                <div className="h-8 w-48 bg-gray-200 rounded mb-6"></div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {Array.from({ length: 3 }, (_, i) => (
                        <div key={i} className="bg-gray-200 rounded-lg h-40"></div>
                    ))}
                </div>
            </div>

            {/* Test Sessions Section Loading */}
            <div className="mb-6">
                <div className="flex justify-between items-center mb-6">
                    <div className="h-8 w-48 bg-gray-200 rounded"></div>
                    <div className="h-10 w-32 bg-gray-200 rounded"></div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {Array.from({ length: 6 }, (_, i) => (
                        <div key={i} className="bg-gray-200 rounded-lg h-32"></div>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default function LoopTalkPage() {
    return (
        <LoopTalkLayout>
            <Suspense fallback={<LoopTalkLoading />}>
                <PageContent />
            </Suspense>
        </LoopTalkLayout>
    );
}
