import type { ThreadOptions, ThreadOptionsUpdate } from "#/queries/threads";

export type ThreadOptionsValues = ThreadOptions & { discord_webhook: string };

const booleanOptions = [
	"sticky",
	"locked",
	"allow_public_posting",
	"allow_rolls",
	"allow_draws",
] as const;

// Only the options that differ from where the form started, so the API checks
// permissions for what actually changed. Undefined when nothing did.
export function changedThreadOptions(
	initial: ThreadOptionsValues,
	current: ThreadOptionsValues,
): ThreadOptionsUpdate | undefined {
	const changes: ThreadOptionsUpdate = {};
	for (const key of booleanOptions) {
		if (current[key] !== initial[key]) changes[key] = current[key];
	}
	const webhook = current.discord_webhook.trim();
	if (webhook !== initial.discord_webhook.trim()) changes.discord_webhook = webhook;
	return Object.keys(changes).length > 0 ? changes : undefined;
}
