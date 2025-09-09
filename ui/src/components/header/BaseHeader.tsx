"use client";

import { CircleDollarSign, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import React from 'react';

import { useUserConfig } from '@/context/UserConfigContext';
import { useAuth } from '@/lib/auth';

// Conditionally load Stack components only when using Stack auth
const StackUserButton = React.lazy(() =>
    import('@stackframe/stack').then(mod => ({ default: mod.UserButton }))
);
const StackTeamSwitcher = React.lazy(() =>
    import('@stackframe/stack').then(mod => ({ default: mod.SelectedTeamSwitcher }))
);

interface BaseHeaderProps {
    headerActions?: React.ReactNode,
    backButton?: React.ReactNode,
    showFeaturesNav?: boolean
}

export default function BaseHeader({ headerActions, backButton, showFeaturesNav = true }: BaseHeaderProps) {
    const { loading, permissions } = useUserConfig();
    const { provider, user } = useAuth();
    const pathname = usePathname();
    const router = useRouter();

    const isActive = (path: string) => {
        return pathname.startsWith(path);
    };

    const hasAdminPermission = Array.isArray(permissions) && permissions.some(p => p.id === 'admin');


    return (
        <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-white">
            <div className="container mx-auto px-4 py-4">
                <nav className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Link href="/" className="text-xl font-semibold text-gray-800 hover:text-gray-600">
                            Dograh
                        </Link>
                        {backButton}
                        {showFeaturesNav && (
                            <div className="flex items-center gap-4 ml-8">
                                {hasAdminPermission && (
                                    <>
                                        <Link
                                            href="/workflow"
                                            className={`text-sm font-medium transition-colors hover:text-primary ${isActive('/workflow') ? 'text-primary' : 'text-gray-600'
                                                }`}
                                        >
                                            Workflows
                                        </Link>
                                        <Link
                                            href="/campaigns"
                                            className={`text-sm font-medium transition-colors hover:text-primary ${isActive('/campaigns') ? 'text-primary' : 'text-gray-600'
                                                }`}
                                        >
                                            Campaigns
                                        </Link>
                                        <Link
                                            href="/automation"
                                            className={`text-sm font-medium transition-colors hover:text-primary ${isActive('/automation') ? 'text-primary' : 'text-gray-600'
                                                }`}
                                        >
                                            Automation
                                        </Link>
                                        <Link
                                            href="/looptalk"
                                            className={`text-sm font-medium transition-colors hover:text-primary ${isActive('/looptalk') ? 'text-primary' : 'text-gray-600'
                                                }`}
                                        >
                                            LoopTalk
                                        </Link>
                                    </>
                                )}
                                <Link
                                    href="/usage"
                                    className={`text-sm font-medium transition-colors hover:text-primary ${isActive('/usage') ? 'text-primary' : 'text-gray-600'
                                        }`}
                                >
                                    Usage
                                </Link>
                                <Link
                                    href="/reports"
                                    className={`text-sm font-medium transition-colors hover:text-primary ${isActive('/reports') ? 'text-primary' : 'text-gray-600'
                                        }`}
                                >
                                    Reports
                                </Link>
                                <Link
                                    href="/api-keys"
                                    className={`text-sm font-medium transition-colors hover:text-primary ${isActive('/api-keys') ? 'text-primary' : 'text-gray-600'
                                        }`}
                                >
                                    Developers
                                </Link>
                            </div>
                        )}
                    </div>
                    <div className="flex-1 flex justify-center">
                        {headerActions}
                    </div>

                    {/* Use key to force remount when user changes to avoid hooks issues */}
                    <div className="flex items-center gap-5" key={user ? 'logged-in' : 'logged-out'}>
                        {provider === 'stack' ? (
                            <React.Suspense fallback={<Loader2 className="w-5 h-5 animate-spin text-gray-600" />}>
                                {!loading && (
                                    <StackTeamSwitcher
                                        onChange={() => {
                                            router.refresh();
                                        }}
                                    />
                                )}
                                <StackUserButton
                                    extraItems={[{
                                        text: 'Usage',
                                        icon: <CircleDollarSign strokeWidth={2} size={16} />,
                                        onClick: () => router.push('/usage')
                                    }]}
                                />
                            </React.Suspense>
                        ) : (
                            <div className="text-sm text-gray-600">
                                Github Star Link
                            </div>
                        )}
                    </div>
                </nav>
            </div>
        </header>
    );
}
