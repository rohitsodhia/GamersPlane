import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { z } from "zod";
import Paginate from "#/components/Paginate";
import { requireAcpPermission } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	sendActivationLink,
	toggleUserBan,
	type UserListRow,
	usersListQueryOptions,
} from "#/queries/users";
import styles from "./users.module.css";

export const Route = createFileRoute("/acp/users")({
	loader: requireAcpPermission("manage_users"),
	component: RouteComponent,
	validateSearch: z.object({
		page: z.number().optional(),
		q: z.string().optional(),
	}),
});

function UserRow({ user }: { user: UserListRow }) {
	const queryClient = useQueryClient();
	const activation = useMutation({ mutationFn: () => sendActivationLink(user.id) });
	const ban = useMutation({
		mutationFn: () => toggleUserBan(user.id),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "list"] }),
	});

	return (
		<div className={styles.row}>
			<span className={styles.username}>{user.username}</span>
			<div className={styles.actions}>
				{!user.activated && (
					<button
						type="button"
						onClick={() => activation.mutate()}
						disabled={activation.isPending}
					>
						Activation Link
					</button>
				)}
				{/* user 1 is the protected system account and can't be banned */}
				{user.id !== 1 && (
					<button type="button" onClick={() => ban.mutate()} disabled={ban.isPending}>
						{user.banned ? "Unban" : "Ban"}
					</button>
				)}
			</div>
		</div>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { page: searchPage, q } = Route.useSearch();
	const navigate = Route.useNavigate();

	const [page, setPage] = useState(searchPage ?? 1);
	const [searchInput, setSearchInput] = useState(q ?? "");
	const prefix = q?.trim() || undefined;

	const { data, isPending, isError } = useQuery(
		usersListQueryOptions({ page, prefix }),
	);

	const submitSearch = (event: FormEvent) => {
		event.preventDefault();
		const next = searchInput.trim();
		setPage(1);
		navigate({
			search: (prev) => ({ ...prev, q: next || undefined, page: undefined }),
		});
	};

	const pagination = data ? (
		<Paginate numItems={data.count} current={page} onPageChange={setPage} />
	) : null;

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				Manage Users
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<form className={styles.search} onSubmit={submitSearch}>
					<input
						type="text"
						placeholder="Username search"
						value={searchInput}
						onChange={(event) => setSearchInput(event.target.value)}
					/>
					<button type="submit" className="skew-btn">
						Search
					</button>
				</form>

				{isPending && <div className="loading">Loading...</div>}
				{isError && <div>Failed to load users.</div>}

				{data && (
					<>
						{pagination}
						{data.users.length === 0 ? (
							<div className={styles["no-results"]}>No users</div>
						) : (
							<div className={styles.list}>
								{data.users.map((user) => (
									<UserRow key={user.id} user={user} />
								))}
							</div>
						)}
						{pagination}
					</>
				)}
			</div>
		</div>
	);
}
