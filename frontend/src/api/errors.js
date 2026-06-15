export function normalizeApiError(error, fallbackMessage = "請求失敗") {
  const payloadError = error?.payload?.error;
  return {
    message: payloadError?.message || fallbackMessage || error?.message || "請求失敗",
    details: payloadError?.details || "",
    code: payloadError?.code || "",
    request_id: typeof error?.payload?.request_id === "string" ? error.payload.request_id : "",
    route: typeof error?.payload?.route === "string" ? error.payload.route : "",
    reason: typeof error?.payload?.reason === "string" ? error.payload.reason : "",
    retry_after_seconds:
      typeof error?.payload?.retry_after_seconds === "number" ? error.payload.retry_after_seconds : 0,
    next_allowed_at:
      typeof error?.payload?.next_allowed_at === "string" ? error.payload.next_allowed_at : null
  };
}
