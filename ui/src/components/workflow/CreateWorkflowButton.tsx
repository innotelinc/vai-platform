'use client';

import { PlusIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Button } from "@/components/ui/button";

export function CreateWorkflowButton() {
    const router = useRouter();
    const handleClick = () => {
        router.push('/create-workflow');
    };

    return (
        <Button
            onClick={handleClick}
        >
            <PlusIcon className="w-4 h-4" />
            Create Workflow
        </Button>
    );
}
