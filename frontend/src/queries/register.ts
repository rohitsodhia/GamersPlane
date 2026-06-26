import { ApiError, apiFetch } from "#/lib/api";

export const register = async (registrationData: {
	username: string;
	email: string;
	password: string;
}) => {
	const res = await apiFetch("/auth/register", {
		method: "POST",
		body: JSON.stringify(registrationData),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const resendActivation = async (data: { email: string }) => {
	const res = await apiFetch("/auth/resendActivation", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
