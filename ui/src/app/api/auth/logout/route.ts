import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';

const OSS_TOKEN_COOKIE = 'dograh_auth_token';
const OSS_USER_COOKIE = 'dograh_auth_user';

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();

  cookieStore.set(OSS_TOKEN_COOKIE, '', {
    httpOnly: true,
    secure: request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim() === 'https',
    sameSite: 'lax',
    maxAge: 0,
    path: '/',
  });

  cookieStore.set(OSS_USER_COOKIE, '', {
    httpOnly: true,
    secure: request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim() === 'https',
    sameSite: 'lax',
    maxAge: 0,
    path: '/',
  });

  return NextResponse.json({ success: true });
}
