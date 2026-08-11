import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { z } from "zod";
import { requireAuth } from "#/lib/auth-route";
import { meQueryOptions } from "#/queries/me";
import { pmQueryOptions } from "#/queries/pms";
import { PmHistory } from "#/routes/pms/-history-pm";
import { PmForm } from "#/routes/pms/-pm-form";

export const Route = createFileRoute("/pms/reply")({
	beforeLoad: requireAuth,
	validateSearch: z.object({
		pmId: z.number(),
	}),
	loaderDeps: ({ search }) => ({ pmId: search.pmId }),
	loader: async ({ context, deps }) => {
		try {
			await Promise.all([
				context.queryClient.ensureQueryData(
					pmQueryOptions(deps.pmId, { includeSelfHistory: true }),
				),
				context.queryClient.ensureQueryData(meQueryOptions),
			]);
		} catch {
			throw redirect({ to: "/pms" });
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { pmId } = Route.useSearch();
	const { data: pm } = useSuspenseQuery(
		pmQueryOptions(pmId, { includeSelfHistory: true }),
	);
	const { data: me } = useSuspenseQuery(meQueryOptions);

	const replyTo = pm.sender.id === me.id ? pm.recipient : pm.sender;
	const replyTitle = pm.title.startsWith("Re: ") ? pm.title : `Re: ${pm.title}`;

	return (
		<>
			<PmForm
				title="Reply to Private Message"
				defaultUsername={replyTo.username}
				defaultTitle={replyTitle}
				replyToId={pm.id}
				history={pm.history}
			/>

			<PmHistory pms={pm.history} />
		</>
	);
}
