import { useForm } from "@tanstack/react-form";
import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Select } from "#/components/Select";
import {
	type ChildForum,
	createSubforum,
	deleteForum,
	type ForumType,
	forumQueryOptions,
	isGameRootForum,
	PROTECTED_FORUM_IDS,
	reorderSubforums,
} from "#/queries/forums";
import styles from "../acp.module.css";
import { ErrorBanner, errorList } from "./-acp-shared";

export const Route = createFileRoute("/acp/forums/$forumId/subforums")({
	component: RouteComponent,
});

const TYPE_OPTIONS: { value: ForumType; label: string }[] = [
	{ value: "f", label: "Forum" },
	{ value: "c", label: "Category" },
];

// Game forums come and go with their games.
const canDelete = (forum: ChildForum) =>
	!PROTECTED_FORUM_IDS.includes(forum.id) && !isGameRootForum(forum);

function RouteComponent() {
	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));
	const queryClient = useQueryClient();
	const refresh = () => queryClient.invalidateQueries({ queryKey: ["forums"] });

	const subforums = [...forum.children].sort((a, b) => a.order - b.order);

	const [listErrors, setListErrors] = useState<string[]>([]);
	const [busy, setBusy] = useState(false);
	const [confirmingDelete, setConfirmingDelete] = useState<number | null>(null);

	const runListAction = async (action: () => Promise<unknown>) => {
		setListErrors([]);
		setBusy(true);
		try {
			await action();
			await refresh();
		} catch (exception) {
			setListErrors(errorList(exception));
		} finally {
			setBusy(false);
		}
	};

	const move = (index: number, offset: -1 | 1) => {
		const ids = subforums.map((subforum) => subforum.id);
		[ids[index], ids[index + offset]] = [ids[index + offset], ids[index]];
		runListAction(() => reorderSubforums(forumId, ids));
	};

	const confirmDelete = (subforumId: number) =>
		runListAction(async () => {
			await deleteForum(subforumId);
			setConfirmingDelete(null);
		});

	const [createErrors, setCreateErrors] = useState<string[]>([]);
	const createForm = useForm({
		defaultValues: {
			title: "",
			forumType: "f" as ForumType,
		},
		onSubmit: async ({ value }) => {
			setCreateErrors([]);
			if (value.title.trim().length < 3) {
				setCreateErrors(["The title must be at least 3 characters."]);
				return;
			}
			try {
				await createSubforum(forumId, {
					title: value.title,
					forum_type: value.forumType,
				});
				createForm.reset();
				await refresh();
			} catch (exception) {
				setCreateErrors(errorList(exception));
			}
		},
	});

	return (
		<div>
			<ErrorBanner errors={listErrors} />
			{subforums.length === 0 ? (
				<p>No subforums.</p>
			) : (
				<ul className={styles["subforum-list"]}>
					{subforums.map((subforum, index) => (
						<li key={subforum.id}>
							<div className={styles["subforum-row"]}>
								<button
									type="button"
									title="Move up"
									disabled={busy || index === 0}
									onClick={() => move(index, -1)}
								>
									↑
								</button>
								<button
									type="button"
									title="Move down"
									disabled={busy || index === subforums.length - 1}
									onClick={() => move(index, 1)}
								>
									↓
								</button>
								<span>
									<Link to="/acp/forums/$forumId" params={{ forumId: subforum.id }}>
										{subforum.title}
									</Link>
									{subforum.forum_type === "c" && " (Category)"}
								</span>
								{canDelete(subforum) && confirmingDelete !== subforum.id && (
									<button
										type="button"
										disabled={busy}
										onClick={() => setConfirmingDelete(subforum.id)}
									>
										Delete
									</button>
								)}
							</div>
							{confirmingDelete === subforum.id && (
								<div className={styles["delete-confirm"]}>
									<p>
										Delete <strong>{subforum.title}</strong>? Its subforums, threads and
										posts go with it.
									</p>
									<div className={styles["save-row"]}>
										<button
											type="button"
											className="skew-btn"
											disabled={busy}
											onClick={() => confirmDelete(subforum.id)}
										>
											Delete
										</button>
										<button
											type="button"
											disabled={busy}
											onClick={() => setConfirmingDelete(null)}
										>
											Cancel
										</button>
									</div>
								</div>
							)}
						</li>
					))}
				</ul>
			)}

			<section className={styles["role-section"]}>
				<h3>New subforum</h3>
				<ErrorBanner errors={createErrors} />
				<form
					className={styles["role-form"]}
					onSubmit={(e) => {
						e.preventDefault();
						createForm.handleSubmit();
					}}
				>
					<createForm.Field name="title">
						{(field) => (
							<div>
								<label htmlFor="new-subforum-title">Title</label>
								<input
									id="new-subforum-title"
									type="text"
									maxLength={200}
									value={field.state.value}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						)}
					</createForm.Field>
					<createForm.Field name="forumType">
						{(field) => (
							<div>
								<label htmlFor="new-subforum-type">Type</label>
								<Select
									id="new-subforum-type"
									items={TYPE_OPTIONS}
									getId={(option) => option.value}
									getLabel={(option) => option.label}
									selectedId={field.state.value}
									onChange={(value) => field.handleChange(value as ForumType)}
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
