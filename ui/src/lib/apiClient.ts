import type { CreateClientConfig } from '@/client/client.gen';

export const createClientConfig: CreateClientConfig = (config) => {
    // Use different URLs for server-side vs client-side
    const isServer = typeof window === 'undefined';
    const baseUrl = isServer
        ? process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL
        : process.env.NEXT_PUBLIC_BACKEND_URL;

    return {
        ...config,
        baseUrl,
    };
};
