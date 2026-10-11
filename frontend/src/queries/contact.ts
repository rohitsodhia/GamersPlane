import { ApiError, apiFetch } from "#/lib/api";

export type ContactData = {
	name: string;
	email: string;
	username: string;
	subject: string;
	message: string;
	// Honeypot; real visitors never fill it
	website: string;
};

export const sendContact = async (data: ContactData) => {
	const res = await apiFetch("/contact", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
