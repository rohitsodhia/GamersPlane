import { useForm } from "@tanstack/react-form";
import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { useState } from "react";
import { Checkbox } from "#/components/Checkbox";
import { FadeOut } from "#/components/FadeOut";
import { useFlash } from "#/lib/use-flash";
import {
	createGameRole,
	deleteGameRole,
	type GameRole,
	gameRolesQueryOptions,
	type RoleMember,
	renameGameRole,
	setGameRoleMembers,
} from "#/queries/forum-acp";
import { forumQueryOptions, isGameRootForum } from "#/queries/forums";
import styles from "../acp.module.css";
import { ErrorBanner, errorList } from "./-acp-shared";

export const Route = createFileRoute("/acp/forums/$forumId/roles")({
	loader: async ({ context, params }) => {
		const forum = await context.queryClient.ensureQueryData(
			forumQueryOptions(params.forumId),
		);
		if (!isGameRootForum(forum)) {
			throw redirect({ to: "/acp/forums/$forumId", params });
		}
		await context.queryClient.ensureQueryData(gameRolesQueryOptions(params.forumId));
	},
	component: RouteComponent,
});

const NAME_MAX_LENGTH = 64;

const validateRoleName = (name: string): string | null => {
	const length = name.trim().length;
	if (length < 1 || length > NAME_MAX_LENGTH) {
		return `The role name must be 1 to ${NAME_MAX_LENGTH} characters.`;
	}
	return null;
};

function PlayerRoleCard({ members }: { members: RoleMember[] }) {
	return (
		<section className={styles["role-section"]}>
			<h3>Players</h3>
			<p>Membership follows the game's player list.</p>
			{members.length === 0 ? (
				<p>No players yet.</p>
			) : (
				<ul className={styles["member-list"]}>
					{members.map((member) => (
						<li key={member.id}>{member.username}</li>
					))}
				</ul>
			)}
		</section>
	);
}

function CustomRoleCard({
	forumId,
	role,
	players,
}: {
	forumId: number;
	role: GameRole;
	players: RoleMember[];
}) {
	const queryClient = useQueryClient();
	const refresh = () => queryClient.invalidateQueries({ queryKey: ["forums"] });

	const [name, setName] = useState(role.name);
	const [memberIds, setMemberIds] = useState<number[]>(
		role.members.map((member) => member.id),
	);
	const [errors, setErrors] = useState<string[]>([]);
	const [busy, setBusy] = useState(false);
	const [confirmingDelete, setConfirmingDelete] = useState(false);
	const [renamed, flashRenamed] = useFlash();
	const [membersSaved, flashMembersSaved] = useFlash();

	const run = async (action: () => Promise<unknown>, onDone?: () => void) => {
		setErrors([]);
		setBusy(true);
		try {
			await action();
			await refresh();
			onDone?.();
		} catch (exception) {
			setErrors(errorList(exception));
		} finally {
			setBusy(false);
		}
	};

	const rename = () => {
		const problem = validateRoleName(name);
		if (problem) {
			setErrors([problem]);
			return;
		}
		run(() => renameGameRole(forumId, role.id, name.trim()), flashRenamed);
	};

	const toggleMember = (playerId: number, checked: boolean) =>
		setMemberIds((current) =>
			checked ? [...current, playerId] : current.filter((id) => id !== playerId),
		);

	return (
		<section className={styles["role-section"]}>
			<h3>{role.name}</h3>
			<ErrorBanner errors={errors} />
			<form
				className={styles["role-form"]}
				onSubmit={(e) => {
					e.preventDefault();
					rename();
				}}
			>
				<div>
					<label htmlFor={`role-name-${role.id}`}>Name</label>
					<input
						id={`role-name-${role.id}`}
						type="text"
						maxLength={NAME_MAX_LENGTH}
						value={name}
						onChange={(e) => setName(e.target.value)}
					/>
				</div>
				<div className={styles["save-row"]}>
					<button type="submit" className="skew-btn" disabled={busy}>
						Save
					</button>
					<FadeOut active={renamed}>Saved</FadeOut>
				</div>
			</form>

			<h4>Members</h4>
			{players.length === 0 ? (
				<p>This game has no players yet.</p>
			) : (
				<>
					<ul className={styles["member-checklist"]}>
						{players.map((player) => (
							<li key={player.id}>
								<Checkbox
									id={`role-${role.id}-player-${player.id}`}
									checked={memberIds.includes(player.id)}
									onChange={(checked) => toggleMember(player.id, checked)}
								/>
								<label htmlFor={`role-${role.id}-player-${player.id}`}>
									{player.username}
								</label>
							</li>
						))}
					</ul>
					<div className={styles["save-row"]}>
						<button
							type="button"
							className="skew-btn"
							disabled={busy}
							onClick={() =>
								run(
									() => setGameRoleMembers(forumId, role.id, memberIds),
									flashMembersSaved,
								)
							}
						>
							Save members
						</button>
						<FadeOut active={membersSaved}>Saved</FadeOut>
					</div>
				</>
			)}

			<div className={styles["role-delete"]}>
				{confirmingDelete ? (
					<div>
						<p>
							Delete <strong>{role.name}</strong>? Its members lose whatever this role
							grants.
						</p>
						<div className={styles["save-row"]}>
							<button
								type="button"
								className="skew-btn"
								disabled={busy}
								onClick={() => run(() => deleteGameRole(forumId, role.id))}
							>
								Delete
							</button>
							<button
								type="button"
								disabled={busy}
								onClick={() => setConfirmingDelete(false)}
							>
								Cancel
							</button>
						</div>
					</div>
				) : (
					<button
						type="button"
						disabled={busy}
						onClick={() => setConfirmingDelete(true)}
					>
						Delete role
					</button>
				)}
			</div>
		</section>
	);
}

function RouteComponent() {
	const { forumId } = Route.useParams();
	const { data } = useSuspenseQuery(gameRolesQueryOptions(forumId));
	const queryClient = useQueryClient();

	const playerRole = data.roles.find((role) => role.kind === "player");
	const customRoles = data.roles.filter((role) => role.kind === "custom");

	const [createErrors, setCreateErrors] = useState<string[]>([]);
	const createForm = useForm({
		defaultValues: { name: "" },
		onSubmit: async ({ value }) => {
			setCreateErrors([]);
			const problem = validateRoleName(value.name);
			if (problem) {
				setCreateErrors([problem]);
				return;
			}
			try {
				await createGameRole(forumId, value.name.trim());
				createForm.reset();
				await queryClient.invalidateQueries({ queryKey: ["forums"] });
			} catch (exception) {
				setCreateErrors(errorList(exception));
			}
		},
	});

	return (
		<div>
			{playerRole && <PlayerRoleCard members={playerRole.members} />}
			{customRoles.map((role) => (
				<CustomRoleCard
					key={role.id}
					forumId={forumId}
					role={role}
					players={data.players}
				/>
			))}

			<section className={styles["role-section"]}>
				<h3>New role</h3>
				<ErrorBanner errors={createErrors} />
				<form
					className={styles["role-form"]}
					onSubmit={(e) => {
						e.preventDefault();
						createForm.handleSubmit();
					}}
				>
					<createForm.Field name="name">
						{(field) => (
							<div>
								<label htmlFor="new-role-name">Name</label>
								<input
									id="new-role-name"
									type="text"
									maxLength={NAME_MAX_LENGTH}
									value={field.state.value}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						)}
					</createForm.Field>
					<createForm.Subscribe selector={(state) => state.isSubmitting}>
						{(isSubmitting) => (
							<button type="submit" className="skew-btn" disabled={isSubmitting}>
								Add
							</button>
						)}
					</createForm.Subscribe>
				</form>
			</section>
		</div>
	);
}
