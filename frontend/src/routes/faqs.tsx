import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { TiptapContent } from "#/components/TiptapContent";
import { useHbMargined } from "#/lib/use-hb-margined";
import { useScrollToHash } from "#/lib/use-scroll-to-hash";
import { faqsQueryOptions } from "#/queries/faqs";
import styles from "./faqs.module.css";

export const Route = createFileRoute("/faqs")({
	loader: ({ context }) => context.queryClient.ensureQueryData(faqsQueryOptions),
	component: RouteComponent,
});

function RouteComponent() {
	const { data } = useSuspenseQuery(faqsQueryOptions);
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	useScrollToHash([data]);

	// Empty sections are hidden from both the sidebar and the body.
	const sections = data.categories.filter((category) => category.faqs.length > 0);

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				FAQs
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				{sections.length === 0 ? (
					<p className={styles["no-faqs"]}>There are no FAQs yet. Check back soon!</p>
				) : (
					<div className={styles["faqs-wrapper"]}>
						<nav className={styles["sidebar"]}>
							<ul>
								{sections.map((section) => (
									<li key={section.category}>
										<a href={`#${section.category}`}>{section.label}</a>
									</li>
								))}
							</ul>
						</nav>
						<div>
							{sections.map((section) => (
								<section
									key={section.category}
									id={section.category}
									className={styles["section"]}
								>
									<h2 className="headerbar hb-dark">{section.label}</h2>
									{section.faqs.map((faq) => (
										<article key={faq.id} className={styles["faq"]}>
											<h3>{faq.question}</h3>
											<TiptapContent content={faq.answer} />
										</article>
									))}
								</section>
							))}
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
