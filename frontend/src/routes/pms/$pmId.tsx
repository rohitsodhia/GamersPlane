import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, redirect, useNavigate } from "@tanstack/react-router";
import { TiptapContent } from "#/components/TiptapContent";
import { requireAuth } from "#/lib/auth-route";
import { formatDateTime } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { deletePM, pmQueryOptions } from "#/queries/pms";
import { PmHistory } from "#/routes/pms/-history-pm";

export const Route = createFileRoute("/pms/$pmId")({
	beforeLoad: requireAuth,
	loader: async ({ context, params }) => {
		try {
			await context.queryClient.ensureQueryData(pmQueryOptions(Number(params.pmId)));
		} catch {
			throw redirect({ to: "/pms" });
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { pmId } = Route.useParams();
	const { data: pm } = useSuspenseQuery(pmQueryOptions(Number(pmId)));
	const navigate = useNavigate();
	const queryClient = useQueryClient();

	const deletePMMutation = useMutation({
		mutationFn: deletePM,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["pms"] });
			navigate({ to: "/pms" });
		},
	});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Private Message
			</h1>

			<div>
				<Link to="/pms/reply" search={{ pmId: pm.id }} className="skew-btn">
					Reply
				</Link>
				<button
					type="button"
					className="skew-btn delete-pm"
					onClick={() => deletePMMutation.mutate(pm.id)}
				>
					Delete
				</button>
			</div>
			<div id="display-pm" style={{ marginInline: `${hbMargined.margin}px` }}>
				<div>
					<div>Title</div>
					<div>{pm.title}</div>
				</div>
				<div>
					<div>From</div>
					<div>
						<Link
							to="/user/$userId"
							params={{ userId: String(pm.sender.id) }}
							className="username"
						>
							{pm.sender.username}
						</Link>
					</div>
				</div>
				<div>
					<div>To</div>
					<div>
						<Link
							to="/user/$userId"
							params={{ userId: String(pm.recipient.id) }}
							className="username"
						>
							{pm.recipient.username}
						</Link>
					</div>
				</div>
				<div>
					<div>When</div>
					<div>{formatDateTime(pm.datestamp)}</div>
				</div>
				<TiptapContent content={pm.message} className="message" />
			</div>

			<PmHistory pms={pm.history} />
		</div>
	);
}
