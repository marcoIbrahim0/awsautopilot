export const NAVIGATION_FEEDBACK_EVENT = 'app:navigation-feedback-start';

/**
 * Triggers the global navigation loading indicator.
 * Use before client-side router navigation that is not initiated by a Link click.
 */
export function startNavigationFeedback() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(NAVIGATION_FEEDBACK_EVENT));
}
