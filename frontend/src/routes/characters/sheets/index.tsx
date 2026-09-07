import { useForm } from "@tanstack/react-form";
import { useMutation, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Autocomplete } from "#/components/Autocomplete";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import { createCharacterSheet } from "#/queries/characterSheet";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import styles from "./index.module.css";

export const Route = createFileRoute("/characters/sheets/")({
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
	},
	component: RouteComponent,
});

function RouteComponent() {
	const hbMarginedH1 = useHbMargined<HTMLHeadingElement>();
	const hbMarginedH2 = useHbMargined<HTMLHeadingElement>();
	const navigate = useNavigate();
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));
	const mutation = useMutation({ mutationFn: createCharacterSheet });
	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const form = useForm({
		defaultValues: {
			name: "",
			systemId: "",
		},
		onSubmit: async ({ value }) => {
			setApiErrors([]);
			try {
				const result = await mutation.mutateAsync({
					name: value.name,
					system_id: value.systemId,
				});
				navigate({
					to: "/characters/sheets/$sheetId",
					params: { sheetId: result.id },
				});
			} catch (exception) {
				if (exception instanceof ApiError) {
					setApiErrors(exception.errors.map((e) => e.detail));
				}
			}
		},
	});

	return (
		<div>
			<h1 className="headerbar" ref={hbMarginedH1.ref}>
				My Character Sheets
			</h1>

			<h2 className="headerbar" ref={hbMarginedH2.ref}>
				New Sheet
			</h2>
			<div style={{ marginInline: `${hbMarginedH2.margin}px` }}>
				{apiErrors.length > 0 && (
					<div className="banner error-banner">
						<ul>
							{apiErrors.map((error) => (
								<li key={error}>{error}</li>
							))}
						</ul>
					</div>
				)}
				<form
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
					className="grid-layout"
				>
					<form.Field
						name="name"
						validators={{
							onBlur: ({ value }) => (value ? undefined : "Label is required."),
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name} className="center-vertically">
									Name
								</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="text"
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">{field.state.meta.errors[0]}</div>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Field
						name="systemId"
						validators={{
							onChange: ({ value }) => (value ? undefined : "You must pick a system."),
						}}
					>
						{(field) => (
							<div>
								<label htmlFor="system-combo" className="center-vertically">
									System
								</label>
								<div>
									<Autocomplete
										id="system-combo"
										items={systems}
										getId={(system: BasicSystem) => system.id}
										getLabel={(system: BasicSystem) => system.name}
										onAction={(id) => field.handleChange(id)}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">{field.state.meta.errors[0]}</div>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div className="is-container">
								<button
									type="submit"
									className="skew-btn"
									disabled={!canSubmit || mutation.isPending}
								>
									Create
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>
		</div>
	);
}
