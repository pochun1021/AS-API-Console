const unsafeHtmlPattern = /<\s*\/?\s*[a-zA-Z][^>]*>/i;
const unsafeScriptPattern = /<\s*\/?\s*script\b/i;
const unsafeJavascriptUriPattern = /javascript\s*:/i;
const unsafeSqlPattern = /(?:\bunion\b\s+\bselect\b|\bdrop\b\s+\btable\b|\binsert\b\s+\binto\b|\bdelete\b\s+\bfrom\b|--|\/\*)/i;
const unsafeJsPattern = /(?:\bfunction\b\s*\(|=>|\balert\s*\(|\bconsole\.[a-zA-Z_]+\s*\()/i;
const asciiDigitsPattern = /^[0-9]+$/;
const asciiDigitsPartialPattern = /^[0-9]*$/;

export function containsUnsafePersistedText(value) {
  const text = String(value || "");
  return [
    unsafeHtmlPattern,
    unsafeScriptPattern,
    unsafeJavascriptUriPattern,
    unsafeSqlPattern,
    unsafeJsPattern
  ].some((pattern) => pattern.test(text));
}

export function validatePersistedText(value, { required = false } = {}) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return required
      ? { ok: false, reason: "required", value: normalized }
      : { ok: true, reason: "", value: "" };
  }
  if (containsUnsafePersistedText(normalized)) {
    return { ok: false, reason: "unsafe", value: normalized };
  }
  return { ok: true, reason: "", value: normalized };
}

export function isAsciiDigits(value) {
  return asciiDigitsPattern.test(String(value || ""));
}

export function isAsciiDigitsPartial(value) {
  return asciiDigitsPartialPattern.test(String(value || ""));
}

export function shouldAllowDigitsInput(value) {
  return isAsciiDigitsPartial(value);
}

export function shouldAllowDigitsPaste(value) {
  return isAsciiDigits(String(value || "").trim());
}
