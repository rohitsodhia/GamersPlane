import { ApiError, apiFetch } from "#/lib/api";

export const requestPasswordReset = async (data: { email: string }) => {
	const res = await apiFetch("/auth/password_reset", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json().catch(() => ({ errors: [] }));
		throw new ApiError(res.status, errors ?? []);
	}
	return res.json();
};

export const checkResetToken = async (token: string): Promise<boolean> => {
	const res = await apiFetch(`/auth/password_reset?token=${encodeURIComponent(token)}`);
	if (!res.ok) {
		const { errors } = await res.json().catch(() => ({ errors: [] }));
		throw new ApiError(res.status, errors ?? []);
	}
	const { valid_token } = await res.json();
	return valid_token === true;
};

export const resetPassword = async (data: {
	token: string;
	password: string;
	confirm_password: string;
}) => {
	const res = await apiFetch("/auth/password_reset", {
		method: "PATCH",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json().catch(() => ({ errors: [] }));
		throw new ApiError(res.status, errors ?? []);
	}
	return res.json();
};
