import { createFileRoute } from "@tanstack/react-router";
import { requireAuth } from "#/lib/auth-route";
import { PmForm } from "#/routes/pms/-pm-form";

export const Route = createFileRoute("/pms/send")({
	beforeLoad: requireAuth,
	component: RouteComponent,
});

function RouteComponent() {
	return <PmForm title="New Private Message" />;
}
