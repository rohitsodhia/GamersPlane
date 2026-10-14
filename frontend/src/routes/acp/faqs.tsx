import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ConfirmDeleteButton } from "#/components/ConfirmDeleteButton";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { Select } from "#/components/Select";
import { TiptapContent } from "#/components/TiptapContent";
import { requireAcpPermission } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	createFaq,
	deleteFaq,
	type Faq,
	type FaqCategory,
	type FaqInput,
	faqErrorMessage,
	faqsQueryOptions,
	moveFaq,
	updateFaq,
} from "#/queries/faqs";
import styles from "./faqs.module.css";

export const Route = createFileRoute("/acp/faqs")({
	loader: async ({ context }) => {
		await requireAcpPermission("manage_faqs")({ context });
		await context.queryClient.ensureQueryData(faqsQueryOptions);
	},
	component: RouteComponent,
});

// Mirrors the API's limit (api/src/app/faqs/schemas.py)
const QUESTION_MAX = 300;

const fieldMessage = (errors: unknown[]): string | undefined => {
	const first = errors[0];
	if (!first) return undefined;
	return typeof first === "string" ? first : (first as { message?: string }).message;
};

const validateQuestion = ({ value }: { value: string }) => {
	const trimmed = value.trim();
	if (!trimmed) return "Question is required.";
	if (trimmed.length > QUESTION_MAX) {
		return `Question must be ${QUESTION_MAX} characters or fewer.`;
	}
	return undefined;
};

const validateAnswer = ({ value }: { value: FaqInput["answer"] }) =>
	isContentEmpty(value) ? "Answer is required." : undefined;

/** Shared by Add (blank) and Edit (prefilled). `onSubmit` rejects on API failure. */
function FAQForm({
	categories,
	initial,
	submitLabel,
	onSubmit,
	onCancel,
}: {
	categories: FaqCategory[];
	initial?: Faq;
	submitLabel: string;
	onSubmit: (data: FaqInput) => Promise<void>;
	onCancel?: () => void;
}) {
	const [apiError, setApiError] = useState<string | null>(null);
	// Editor only reads its value on mount, so bump this to clear it after an add.
	const [editorKey, setEditorKey] = useState(0);

	const form = useForm({
		defaultValues: {
			category: initial?.category ?? categories[0].category,
			question: initial?.question ?? "",
			answer: initial?.answer ?? emptyContent,
		} as FaqInput,
		onSubmit: async ({ value, formApi }) => {
			setApiError(null);
			try {
				await onSubmit({ ...value, question: value.question.trim() });
			} catch (error) {
				setApiError(faqErrorMessage(error));
				return;
			}
			if (!initial) {
				formApi.reset();
				setEditorKey((key) => key + 1);
			}
		},
	});

	return (
		<form
			className={styles["faq-form"]}
			onSubmit={(e) => {
				e.preventDefault();
				form.handleSubmit();
			}}
		>
			{apiError && <p className="banner error-banner">{apiError}</p>}

			<form.Field name="category">
				{(field) => (
					<div className={styles["field"]}>
						<label htmlFor={`${field.name}-${initial?.id ?? "new"}`}>Category</label>
						<Select
							id={`${field.name}-${initial?.id ?? "new"}`}
							items={categories}
							getId={(category) => category.category}
							getLabel={(category) => category.label}
							selectedId={field.state.value}
							onChange={(id) => field.handleChange(id as FaqInput["category"])}
						/>
					</div>
				)}
			</form.Field>

			<form.Field
				name="question"
				validators={{ onBlur: validateQuestion, onSubmit: validateQuestion }}
			>
				{(field) => {
					const error = fieldMessage(field.state.meta.errors);
					const id = `${field.name}-${initial?.id ?? "new"}`;
					return (
						<div className={styles["field"]}>
							<label htmlFor={id}>Question</label>
							<input
								id={id}
								type="text"
								value={field.state.value}
								onBlur={field.handleBlur}
								onChange={(e) => field.handleChange(e.target.value)}
								autoComplete="off"
							/>
							{error && <p className={styles["field-error"]}>{error}</p>}
						</div>
					);
				}}
			</form.Field>

			<form.Field
				name="answer"
				validators={{
					// The Editor emits onChange when it syncs its content (mount, form
					// reset), so only re-validate on change once the user has left the field.
					onChange: ({ value, fieldApi }) =>
						fieldApi.state.meta.isBlurred ? validateAnswer({ value }) : undefined,
					onBlur: validateAnswer,
					onSubmit: validateAnswer,
				}}
			>
				{(field) => {
					const error = fieldMessage(field.state.meta.errors);
					const id = `${field.name}-${initial?.id ?? "new"}`;
					return (
						<div className={styles["field"]}>
							<label htmlFor={id}>Answer</label>
							<Editor
								key={editorKey}
								id={id}
								value={field.state.value}
								onChange={(value) => field.handleChange(value)}
								onBlur={field.handleBlur}
							/>
							{error && <p className={styles["field-error"]}>{error}</p>}
						</div>
					);
				}}
			</form.Field>

			<form.Subscribe selector={(state) => state.isSubmitting}>
				{(isSubmitting) => (
					<div className={styles["form-actions"]}>
						<button type="submit" className="skew-btn" disabled={isSubmitting}>
							{submitLabel}
						</button>
						{onCancel && (
							<button
								type="button"
								className="skew-btn"
								onClick={onCancel}
								disabled={isSubmitting}
							>
								Cancel
							</button>
						)}
					</div>
				)}
			</form.Subscribe>
		</form>
	);
}

function FAQItem({
	faq,
	isFirst,
	isLast,
	categories,
	isEditing,
	onEdit,
	onStopEditing,
}: {
	faq: Faq;
	isFirst: boolean;
	isLast: boolean;
	categories: FaqCategory[];
	isEditing: boolean;
	onEdit: () => void;
	onStopEditing: () => void;
}) {
	const queryClient = useQueryClient();
	const refetch = () => queryClient.invalidateQueries({ queryKey: ["faqs"] });
	const [actionError, setActionError] = useState<string | null>(null);

	const update = useMutation({ mutationFn: updateFaq, onSuccess: refetch });
	const move = useMutation({
		mutationFn: moveFaq,
		onSuccess: () => {
			setActionError(null);
			return refetch();
		},
		onError: (error) => setActionError(faqErrorMessage(error)),
	});
	const remove = useMutation({
		mutationFn: deleteFaq,
		onSuccess: () => {
			setActionError(null);
			return refetch();
		},
		onError: (error) => setActionError(faqErrorMessage(error)),
	});

	if (isEditing) {
		return (
			<div className={styles["faq-item"]}>
				<FAQForm
					categories={categories}
					initial={faq}
					submitLabel="Save"
					onCancel={onStopEditing}
					onSubmit={async (data) => {
						await update.mutateAsync({ id: faq.id, ...data });
						onStopEditing();
					}}
				/>
			</div>
		);
	}

	const busy = move.isPending || remove.isPending;

	return (
		<div className={styles["faq-item"]}>
			<div className={styles["faq-header"]}>
				<h4>{faq.question}</h4>
				<div className={styles["faq-actions"]}>
					<button
						type="button"
						aria-label="Move up"
						disabled={isFirst || busy}
						onClick={() => move.mutate({ id: faq.id, direction: "up" })}
					>
						▲
					</button>
					<button
						type="button"
						aria-label="Move down"
						disabled={isLast || busy}
						onClick={() => move.mutate({ id: faq.id, direction: "down" })}
					>
						▼
					</button>
					<button type="button" onClick={onEdit} disabled={busy}>
						Edit
					</button>
					<ConfirmDeleteButton
						label="Delete FAQ"
						message="Delete this FAQ? This can't be undone."
						isDisabled={busy}
						onConfirm={() => remove.mutate(faq.id)}
					/>
				</div>
			</div>
			{actionError && <p className="banner error-banner">{actionError}</p>}
			<TiptapContent content={faq.answer} />
		</div>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { data } = useSuspenseQuery(faqsQueryOptions);
	const queryClient = useQueryClient();
	const [editingId, setEditingId] = useState<number | null>(null);

	const create = useMutation({
		mutationFn: createFaq,
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["faqs"] }),
	});

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				Manage FAQs
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<section className={styles["add-section"]}>
					<h3>Add FAQ</h3>
					<FAQForm
						categories={data.categories}
						submitLabel="Add FAQ"
						onSubmit={async (input) => {
							await create.mutateAsync(input);
						}}
					/>
				</section>

				{data.categories.map((category) => (
					<section key={category.category} className={styles["category"]}>
						<h3>{category.label}</h3>
						{category.faqs.length === 0 ? (
							<p className={styles["no-questions"]}>No questions yet</p>
						) : (
							category.faqs.map((faq, index) => (
								<FAQItem
									key={faq.id}
									faq={faq}
									isFirst={index === 0}
									isLast={index === category.faqs.length - 1}
									categories={data.categories}
									isEditing={editingId === faq.id}
									onEdit={() => setEditingId(faq.id)}
									onStopEditing={() => setEditingId(null)}
								/>
							))
						)}
					</section>
				))}
			</div>
		</div>
	);
}
