/**
 * @typedef {{ code: string, message: string }} ApiError
 * @typedef {{ id: string, status: 'active'|'revoked'|'expired', masked_key: string, key_prefix: string, application_date: string, duration_months: number, expires_at: string, owner_account?: string, owner_name?: string }} ApiKeyListItem
 * @typedef {ApiKeyListItem & { created_at: string, purpose?: string, department?: string }} ApiKeyDetail
 * @typedef {{ id: string, email: string, account?: string, sysid?: string, name?: string, status: 'active'|'inactive', remark: string, created_at: string, updated_at: string }} WhitelistItem
 * @typedef {{ id: string, account: string, sysid: string, name: string, email: string, role: 'user'|'admin' }} UserSearchItem
 */
