/**
 * errorReporter.tsx - Frontend error reporting to centralized ErrorHandler
 *
 * Bridges frontend catch blocks to backend ErrorHandler so all errors
 * appear in the Error Panel, not just backend ones.
 *
 * Usage:
 *   import { reportError } from '../utils/errorReporter';
 *
 *   try {
 *     await fetch(...)
 *   } catch (error) {
 *     reportError({
 *       source: 'ServiceStatusPanel',
 *       operation: 'fetchLLMStatus',
 *       message: error instanceof Error ? error.message : String(error),
 *       context: 'service: llm',
 *       severity: 'medium'
 *     });
 *   }
 */

const API_BASE = 'http://localhost:8000';

export type ErrorSeverity = 'critical' | 'high' | 'medium' | 'low' | 'trace';

export interface ErrorReport {
  source: string;      // Component name: ServiceStatusPanel, App, SidebarsPanel
  operation: string;   // What was attempted: fetchLLMStatus, sendMessage, spawnSidebar
  message: string;     // The actual error message
  context?: string;    // Additional context: service name, sidebar ID, etc.
  severity?: ErrorSeverity;  // Defaults to 'medium'
}

export interface ErrorReportResult {
  success: boolean;
  error_id?: string;
  category?: string;
  severity?: string;
  fallback?: boolean;  // True if we couldn't reach the API
}

/**
 * Report a frontend error to the centralized ErrorHandler.
 *
 * Gracefully degrades: if the API is down (which is often WHY we have an error),
 * it logs to console and returns a fallback result instead of throwing.
 */
export async function reportError(report: ErrorReport): Promise<ErrorReportResult> {
  // Ensure message is a string
  const message = typeof report.message === 'string'
    ? report.message
    : String(report.message);

  const payload = {
    source: report.source,
    operation: report.operation,
    message: message,
    context: report.context || null,
    severity: report.severity || 'medium'
  };

  // Debug logging for tracing error flow
  console.log(`[errorReporter] Reporting: [${report.source}] ${report.operation} (${report.severity || 'medium'})`);
  if (report.context) {
    console.log(`[errorReporter]   Context: ${report.context}`);
  }

  try {
    const response = await fetch(`${API_BASE}/errors/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(3000)  // Don't hang if API is down
    });

    if (response.ok) {
      const data = await response.json();
      console.log(`[errorReporter] ✓ Reported successfully: ${data.error_id}`);
      return {
        success: true,
        error_id: data.error_id,
        category: data.category,
        severity: data.severity
      };
    } else {
      // API returned error - log but don't throw
      console.error(`[errorReporter] ✗ API returned ${response.status}:`, await response.text());
      return { success: false, fallback: true };
    }
  } catch (err) {
    // Network error or timeout - expected when API is the problem
    console.error(`[errorReporter] Could not reach API:`, err);
    console.error(`[errorReporter] Original error: [${report.source}] ${report.operation}: ${message}`);
    return { success: false, fallback: true };
  }
}

/**
 * Helper to extract error message from unknown catch value.
 * Use in catch blocks: reportError({ message: getErrorMessage(error), ... })
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return String(error);
}

/**
 * Convenience wrapper that combines getErrorMessage + reportError.
 *
 * Usage:
 *   catch (error) {
 *     reportCaughtError(error, 'ServiceStatusPanel', 'fetchLLMStatus', { context: 'llm' });
 *   }
 */
export async function reportCaughtError(
  error: unknown,
  source: string,
  operation: string,
  options?: { context?: string; severity?: ErrorSeverity }
): Promise<ErrorReportResult> {
  return reportError({
    source,
    operation,
    message: getErrorMessage(error),
    context: options?.context,
    severity: options?.severity || 'medium'
  });
}
