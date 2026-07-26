/**
 * formatters.ts — shared display utilities for GreenChain mobile.
 *
 * data_quality_score from backend is 0–100 (confirmed in sensor model).
 * Do NOT multiply these values by 100.
 */

/**
 * Format a 0–100 percentage score (e.g. data_quality_score, risk_score).
 * Returns "N/A" for null/undefined.
 */
export function formatScore(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return 'N/A';
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format a fraction that may be either 0–1 OR 0–100.
 * Heuristic: if value <= 1.0, multiply by 100. Otherwise use as-is.
 * Use ONLY when the backend scale is uncertain (e.g. MRV confidence score).
 * For known 0–100 fields (data_quality_score), use formatScore() directly.
 */
export function formatPercentage(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return 'N/A';
  const pct = value <= 1.0 ? value * 100 : value;
  return `${pct.toFixed(decimals)}%`;
}

/**
 * Shorten a 64-char hash for display.
 * "d1e6d8a303...4509f159"
 */
export function formatHashShort(hash: string, prefixLen = 10, suffixLen = 8): string {
  if (!hash || hash.length <= prefixLen + suffixLen + 3) return hash;
  return `${hash.slice(0, prefixLen)}...${hash.slice(-suffixLen)}`;
}

/**
 * Format a date string in Indian locale.
 */
export function formatDateIN(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}
