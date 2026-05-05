/**
 * @typedef {{ code: string, message: string }} ApiError
 * @typedef {{ id: string, status: 'active'|'revoked'|'expired', masked_key: string, key_prefix: string, application_date: string, duration_months: number, created_at: string, expires_at: string }} ApiKeyListItem
 * @typedef {ApiKeyListItem & { owner_account?: string }} ApiKeyDetail
 * @typedef {{ id: string, email: string, sysid?: string, name?: string, status: 'active'|'inactive', remark: string, created_at: string, updated_at: string }} WhitelistItem
 * @typedef {{ id: string, sysid: string, name: string, email: string }} UserSearchItem
 */
