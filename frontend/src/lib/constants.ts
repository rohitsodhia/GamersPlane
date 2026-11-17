/** Delay (ms) for debouncing user input before firing searches/filters/navigation. */
export const DEBOUNCE_MS = 300;
// Fewest characters a username search needs before it hits the API (too many users
// match a single letter).
export const MIN_USER_SEARCH_LENGTH = 2;

// There is no standard way to opt a field out of password managers, so each one
// needs its own hint. `autocomplete="off"` alone is widely ignored.
export const NO_PASSWORD_MANAGER_ATTRS = {
	"data-lpignore": "true",
	"data-1p-ignore": true,
	"data-bwignore": "true",
	"data-form-type": "other",
	"data-protonpass-ignore": "true",
} as const;
