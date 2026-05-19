/**
 * @typedef {{ code: string, message: string }} ApiError
 * @typedef {{ id: string, status: 'active'|'revoked'|'expired', masked_key: string, key_alias: string, application_date: string, duration_months: number, expires_at: string, owner_account?: string, owner_name?: string }} ApiKeyListItem
 * @typedef {ApiKeyListItem & { created_at: string, purpose?: string, department?: string }} ApiKeyDetail
 * @typedef {{ owner_account: string, owner_name: string, owner_email: string, owner_department: string, total_applications: number, active_count: number, revoked_count: number, expired_count: number, last_applied_at: string }} ApiKeyUserStatisticsItem
 * @typedef {{ id: string, email: string, account?: string, sysid?: number, name?: string, status: 'active'|'inactive', remark: string, created_at: string, updated_at: string }} WhitelistItem
 * @typedef {{ id: string, account: string, sysid: number, name: string, email: string, role: 'user'|'admin' }} UserSearchItem
 */
