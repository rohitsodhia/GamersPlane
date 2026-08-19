import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import Paginate from "#/components/Paginate";
import { useHbMargined } from "#/lib/use-hb-margined";
import { systemsQueryOptions } from "#/queries/systems";
import styles from "./systems.module.css";

export const Route = createFileRoute("/systems")({
	component: RouteComponent,
});

function RouteComponent() {
	const { data: systems } = useSuspenseQuery(systemsQueryOptions());
	const [search, setSearch] = useState("");
	const [debouncedSearch, setDebouncedSearch] = useState("");
	const [page, setPage] = useState(1);
	const ITEMS_PER_PAGE = 10;

	useEffect(() => {
		const timer = setTimeout(() => {
			setDebouncedSearch(search);
			setPage(1);
		}, 300);
		return () => clearTimeout(timer);
	}, [search]);

	const filteredSystems = debouncedSearch
		? systems.filter((s) =>
				s.name.toLowerCase().includes(debouncedSearch.toLowerCase()),
			)
		: systems;

	const paginatedSystems = filteredSystems.slice(
		(page - 1) * ITEMS_PER_PAGE,
		page * ITEMS_PER_PAGE,
	);

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div className={styles["systems-list-page"]}>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Systems on Gamers' Plane
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<div className={`${styles["systems-filter"]} two-column`}>
					<form>
						<label htmlFor="systems-search">Search:</label>
						<input
							id="systems-search"
							type="text"
							value={search}
							onChange={(e) => setSearch(e.target.value)}
						/>
						<p>
							<strong>
								{filteredSystems.length} System{filteredSystems.length > 1 ? "s" : ""}{" "}
								Found
							</strong>
						</p>
					</form>
					<div>
						<Paginate
							numItems={filteredSystems.length}
							itemsPerPage={ITEMS_PER_PAGE}
							current={page}
							onPageChange={setPage}
							disableUpdateUrl
						/>
					</div>
				</div>
				<div className={styles["systems-list"]}>
					{paginatedSystems.map((system) => (
						<div key={system.id} className={styles.system}>
							<div className={styles["left-col"]}>
								<div className={styles.logo}>
									<img
										src={`/images/logos/${system.id}.png`}
										alt={`${system.name} Logo`}
									/>
								</div>
								<p>
									<Link to="/games/list/?system={{system.id}}">Find games</Link>
								</p>
								<p>
									<Link to="/games/new/?system={{system.id}}">Start a game</Link>
								</p>
							</div>
							<div className="info">
								<h2>{system.name}</h2>
								{system.name === "Custom" && (
									<div>
										Play any type of game you want, from niche indie games to that one
										big system we forgot to list. You will have the option to freely
										enter any system name you want to your game.
									</div>
								)}
								{system.name !== "Custom" && (
									<>
										{system.publisher?.name &&
											((system.publisher.website && (
												<p className="publisher">
													Publisher:{" "}
													<a href={system.publisher.website} target="_blank">
														{system.publisher.name}
													</a>
												</p>
											)) || (
												<p className="publisher">
													Publisher: <span>{system.publisher.name}</span>
												</p>
											))}
										{system.genres && (
											<p className="genres">
												Genre<span ng-if="system.genres.length > 1">s</span>:{" "}
												{system.genres.map((genre) => genre).join(", ")}
											</p>
										)}
										{system.basics.length > 0 && (
											<div className="basics">
												<h3>Buy the Basics!</h3>
												{system.basics.map((basic) => (
													<p key={basic.url}>
														<a href={basic.url} target="_blank">
															{basic.label}
														</a>
													</p>
												))}
											</div>
										)}
									</>
								)}
							</div>
						</div>
					))}
					{paginatedSystems.length === 0 && (
						<div className={styles["no-results"]}>No systems found</div>
					)}
				</div>
				<div className="align-right">
					<Paginate
						numItems={filteredSystems.length}
						itemsPerPage={ITEMS_PER_PAGE}
						current={page}
						onPageChange={setPage}
						disableUpdateUrl
					/>
				</div>
			</div>
		</div>
	);
}
