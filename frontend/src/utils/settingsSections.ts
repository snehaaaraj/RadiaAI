export const SETTINGS_SECTION_IDS = {
  JAMA_ACCOUNT: 'jama-account',
  DOCUMENT_INGESTION: 'document-ingestion',
  THEME_MODE: 'theme-mode',
  STARTUP_BEHAVIOR: 'startup-behavior',
  REVIEW_NOTIFICATIONS: 'review-notifications',
  RESET_PERSONALIZATION: 'reset-personalization',
} as const;

export const SETTINGS_SECTION_ITEMS = [
  { id: SETTINGS_SECTION_IDS.JAMA_ACCOUNT, label: 'Jama account' },
  { id: SETTINGS_SECTION_IDS.DOCUMENT_INGESTION, label: 'Document ingestion' },
  { id: SETTINGS_SECTION_IDS.THEME_MODE, label: 'Theme mode' },
  { id: SETTINGS_SECTION_IDS.STARTUP_BEHAVIOR, label: 'Startup behavior' },
  { id: SETTINGS_SECTION_IDS.REVIEW_NOTIFICATIONS, label: 'Review notifications' },
  { id: SETTINGS_SECTION_IDS.RESET_PERSONALIZATION, label: 'Reset personalization' },
] as const;
