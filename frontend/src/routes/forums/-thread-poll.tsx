import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";
import { Radio, RadioGroup } from "react-aria-components";
import { Checkbox } from "#/components/Checkbox";
import { ApiError } from "#/lib/api";
import { type PollData, threadQueryOptions, voteInPoll } from "#/queries/threads";
import styles from "./-thread-poll.module.css";
import {
	canSubmitVote,
	percentOfVoters,
	plainNote,
	pollView,
	toggleSelection,
} from "./-thread-poll-state";

export function ThreadPoll({
	threadId,
	poll,
	locked,
	loggedIn,
}: {
	threadId: number;
	poll: PollData;
	locked: boolean;
	loggedIn: boolean;
}) {
	const id = useId();
	const queryClient = useQueryClient();
	const [changing, setChanging] = useState(false);
	const [selected, setSelected] = useState<number[]>([]);
	const [errors, setErrors] = useState<string[]>([]);

	const voteMutation = useMutation({
		mutationFn: (optionIds: number[]) => voteInPoll(threadId, optionIds),
		onMutate: () => setErrors([]),
		onSuccess: (updated) => {
			queryClient.setQueryData(threadQueryOptions(threadId).queryKey, (thread) =>
				thread ? { ...thread, poll: updated } : thread,
			);
			setChanging(false);
		},
		onError: (exception) =>
			setErrors(
				exception instanceof ApiError
					? exception.errors.map((e) => e.detail)
					: ["Couldn't save your vote."],
			),
	});

	const view = pollView(poll, changing);
	const max = poll.options_per_user;

	const startChanging = () => {
		setSelected(poll.my_votes);
		setErrors([]);
		setChanging(true);
	};

	return (
		<section className={styles["thread-poll"]} aria-labelledby={`${id}-question`}>
			<div className={styles["poll-header"]}>
				<h2 id={`${id}-question`}>{poll.question}</h2>
				{locked && <span className={styles["poll-closed"]}>Poll closed</span>}
			</div>

			{view === "voting" && (
				<form
					onSubmit={(e) => {
						e.preventDefault();
						voteMutation.mutate(selected);
					}}
				>
					{max > 1 && <p className={styles["poll-hint"]}>Choose up to {max}.</p>}
					{max === 1 ? (
						<RadioGroup
							aria-labelledby={`${id}-question`}
							value={selected[0] === undefined ? null : String(selected[0])}
							onChange={(value) => setSelected([Number(value)])}
							className={styles["poll-choices"]}
						>
							{poll.options.map((option) => (
								<Radio key={option.id} value={String(option.id)}>
									{option.text}
								</Radio>
							))}
						</RadioGroup>
					) : (
						<div className={styles["poll-choices"]}>
							{poll.options.map((option) => (
								<div key={option.id} className={styles["poll-choice"]}>
									<Checkbox
										id={`${id}-option-${option.id}`}
										checked={selected.includes(option.id)}
										disabled={!selected.includes(option.id) && selected.length >= max}
										onChange={() =>
											setSelected((current) => toggleSelection(current, option.id, max))
										}
									/>
									<label htmlFor={`${id}-option-${option.id}`}>{option.text}</label>
								</div>
							))}
						</div>
					)}
					{errors.length > 0 && (
						<div className="error">
							{errors.map((error) => (
								<div key={error}>{error}</div>
							))}
						</div>
					)}
					<div className={styles["poll-actions"]}>
						<button
							type="submit"
							className="skew-btn"
							disabled={!canSubmitVote(selected, max) || voteMutation.isPending}
						>
							Vote
						</button>
						{changing && (
							<button type="button" onClick={() => setChanging(false)}>
								Cancel
							</button>
						)}
					</div>
				</form>
			)}

			{view === "results" && (
				<>
					<ul className={styles["poll-results"]}>
						{poll.options.map((option) => {
							const percent = percentOfVoters(option.votes, poll.total_voters);
							const mine = poll.my_votes.includes(option.id);
							return (
								<li
									key={option.id}
									className={styles["poll-result"]}
									data-mine={mine || undefined}
								>
									<div className={styles["poll-result-label"]}>
										<span>
											{option.text}
											{mine && (
												<span className={styles["poll-mine"]}> (your vote)</span>
											)}
										</span>
										<span className={styles["poll-count"]}>
											{option.votes ?? 0} ({percent}%)
										</span>
									</div>
									<div className={styles["poll-bar"]} aria-hidden="true">
										<div
											className={styles["poll-bar-fill"]}
											style={{ width: `${percent}%` }}
										/>
									</div>
								</li>
							);
						})}
					</ul>
					<div className={styles["poll-actions"]}>
						<span className={styles["poll-count"]}>
							{poll.total_voters} {poll.total_voters === 1 ? "voter" : "voters"}
						</span>
						{poll.can_vote && (
							<button type="button" onClick={startChanging}>
								{poll.voted ? "Change vote" : "Vote"}
							</button>
						)}
					</div>
				</>
			)}

			{view === "plain" && (
				<>
					<ul className={styles["poll-plain"]}>
						{poll.options.map((option) => (
							<li key={option.id}>{option.text}</li>
						))}
					</ul>
					<p className={styles["poll-hint"]}>
						{loggedIn ? (
							plainNote(true)
						) : (
							<Link to="/login" search={{ redirect: `/forums/thread/${threadId}` }}>
								{plainNote(false)}
							</Link>
						)}
					</p>
				</>
			)}
		</section>
	);
}
