/**
 * Application-wide constants.
 * Centralised here so changing a value propagates everywhere automatically.
 */

export const APP_NAME = 'Radia AI';
export const HEADER_HEIGHT = 84;
export const SIDEBAR_WIDTH = 248;
export const SIDEBAR_COLLAPSED_WIDTH = 76;

export const ROUTES = {
  LANDING: '/',
  RADIA_AI_RESOURCES: '/radia-ai',
  JAMA_ROUNDTRIP: '/jama-roundtrip',
  HOME: '/workspace',
  REVIEW_REQUIREMENT: '/review/requirement',
  REVIEW_SET: '/review/set',
  REVIEW_DELTA: '/review/delta',
  REVIEW_HISTORY: '/review/history',
  STANDARDS: '/standards',
  CHAT: '/chat',
  SEARCH: '/search',
  DOCUMENTS: '/documents',
  SETTINGS: '/settings',
} as const;

export const ROUTE_TITLES: Record<string, string> = {
  [ROUTES.LANDING]: 'Launchpad',
  [ROUTES.RADIA_AI_RESOURCES]: 'Radia AI Resources',
  [ROUTES.JAMA_ROUNDTRIP]: 'Jama Roundtrip',
  [ROUTES.HOME]: 'Home',
  [ROUTES.REVIEW_REQUIREMENT]: 'Individual Requirement Review',
  [ROUTES.REVIEW_SET]: 'Set Review',
  [ROUTES.REVIEW_DELTA]: 'Delta Review',
  [ROUTES.REVIEW_HISTORY]: 'Review History',
  [ROUTES.STANDARDS]: 'Standards',
  [ROUTES.CHAT]: 'Chat',
  [ROUTES.SEARCH]: 'Search',
  [ROUTES.DOCUMENTS]: 'Documents',
  [ROUTES.SETTINGS]: 'Settings',
};

export const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? '0.1.0';
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

/** Default number of document chunks to retrieve per query */
export const DEFAULT_TOP_K = 5;

/** Maximum characters to display in a citation snippet */
export const CITATION_SNIPPET_LENGTH = 300;
