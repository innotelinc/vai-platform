/**
 * Centralized disposition codes used throughout the application
 * Update this array when adding new disposition codes
 */
export const DISPOSITION_CODES = [
  'CALLBK',
  'call_duration_exceeded',
  'DAIR',
  'DNC',
  'HU',
  'LB',
  'ND',
  'NIBP',
  'NQ',
  'system_connect_error',
  'unknown',
  'user_disqualified',
  'user_idle_max_duration_exceeded',
  'VM',
  'voicemail_detected',
  'WN',
  'XFER',
] as const;

export type DispositionCode = typeof DISPOSITION_CODES[number];
