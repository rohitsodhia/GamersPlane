import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { requireAuth } from "#/lib/auth-route";
import { searchUserByIdQueryOptions } from "#/queries/users";
import { PmForm } from "#/routes/pms/-pm-form";

export const Route = createFileRoute("/pms/send")({
	beforeLoad: requireAuth,
	validateSearch: z.object({
		userId: z.number().optional(),
	}),
	loaderDeps: ({ search }) => ({ userId: search.userId }),
	loader: async ({ context, deps }) => {
		if (deps.userId !== undefined) {
			await context.queryClient.ensureQueryData(
				searchUserByIdQueryOptions(deps.userId),
			);
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { userId } = Route.useSearch();

	if (userId !== undefined) {
		return <SendToUser userId={userId} />;
	}

	return <PmForm title="New Private Message" />;
}

function SendToUser({ userId }: { userId: number }) {
	const { data: user } = useSuspenseQuery(searchUserByIdQueryOptions(userId));

	return <PmForm title="New Private Message" defaultUsername={user?.username ?? ""} />;
}
