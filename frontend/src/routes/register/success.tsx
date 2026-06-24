import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/register/success")({
	component: RouteComponent,
});

function RouteComponent() {
	return (
		<div>
			<h1 className="headerbar">Thank you for registering!</h1>
			<div className="hb-margined">
				<p>
					An email has been sent to you with instructions on how to activate
					your account.
				</p>
				<p>
					Please make sure <strong>contact@gamersplane.com</strong> is
					whitelisted on your email account. If you do not recieve an email in
					your inbox, please check your spam folder. If you still haven't gotten
					a mail, you can try{" "}
					<a href="/register/resendActivation/">
						resending an activation email
					</a>
					.
				</p>
			</div>
		</div>
	);
}
