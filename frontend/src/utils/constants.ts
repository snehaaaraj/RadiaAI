/**
 * Application-wide constants.
 * Centralised here so changing a value propagates everywhere automatically.
 */

export const APP_NAME = 'Radia AI';

export const ROUTES = {
  HOME: '/',
  CHAT: '/chat',
  SEARCH: '/search',
  DOCUMENTS: '/documents',
  SETTINGS: '/settings',
} as const;

export const API_BASE = '/api/v1';

/** Default number of document chunks to retrieve per query */
export const DEFAULT_TOP_K = 5;

/** Maximum characters to display in a citation snippet */
export const CITATION_SNIPPET_LENGTH = 300;
