import { redirect } from "@tanstack/react-router";
import { useAuthStore } from "#/stores/auth";

export function requireAuth({ location }: { location: { href: string } }) {
	const { token } = useAuthStore.getState();
	if (!token) {
		throw redirect({
			to: "/login",
			search: { redirect: location.href },
		});
	}
	return { token };
}
