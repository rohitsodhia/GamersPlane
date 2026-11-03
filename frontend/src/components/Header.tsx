import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import clsx from "clsx";
import { useCallback, useRef } from "react";
import { buildNotificationItems, dropdownItems } from "#/components/notificationText";
import ThemeToggle from "#/components/ThemeToggle";
import {
	meHeaderQueryOptions,
	meNotificationsQueryOptions,
	meQueryOptions,
} from "#/queries/me";
import { useAuthStore } from "#/stores/auth";
import { useModeratorModeStore } from "#/stores/moderator-mode";
import { useThemeStore } from "#/stores/theme";
import styles from "./Header.module.css";

type PopoverPosition = {
	top: number;
	left?: number;
	right?: number;
	// Distance from the panel's right edge to its triangle, as the --arrow-right
	// CSS variable, for panels whose triangle must line up with the trigger.
	arrowRight?: number;
};

function usePopoverAnchor(position: (rect: DOMRect) => PopoverPosition) {
	const buttonRef = useRef<HTMLButtonElement>(null);
	const positionRef = useRef(position);
	positionRef.current = position;

	const popoverRef = useCallback((node: HTMLUListElement | null) => {
		if (!node || !buttonRef.current) return;
		const popover = node;
		const button = buttonRef.current;
		function onToggle(e: ToggleEvent) {
			if (e.newState === "open") {
				const rect = button.getBoundingClientRect();
				const pos = positionRef.current(rect);
				popover.style.top = `${pos.top}px`;
				if (pos.left !== undefined) popover.style.left = `${pos.left}px`;
				if (pos.right !== undefined) popover.style.right = `${pos.right}px`;
				if (pos.arrowRight !== undefined)
					popover.style.setProperty("--arrow-right", `${pos.arrowRight}px`);
			}
		}
		popover.addEventListener("toggle", onToggle);
		return () => popover.removeEventListener("toggle", onToggle);
	}, []);

	return { buttonRef, popoverRef };
}

function Header() {
	const location = useLocation();
	const theme = useThemeStore((state) => state.theme);

	const logo_path = location.pathname === "/" ? "header_logo" : "logo";

	const token = useAuthStore((state) => state.token);
	const { data: me } = useQuery({ ...meQueryOptions, enabled: !!token });
	const { data: header } = useQuery({ ...meHeaderQueryOptions, enabled: !!token });
	const pmCount = header?.pmCount ?? 0;
	const { data: notifications } = useQuery({
		...meNotificationsQueryOptions,
		enabled: !!token,
	});
	const notificationCount = notifications?.count ?? 0;
	const { shown: shownNotifications, hasMore: hasMoreNotifications } = dropdownItems(
		notifications ? buildNotificationItems(notifications) : [],
	);

	const { buttonRef: toolsButtonRef, popoverRef: toolsPopoverRef } = usePopoverAnchor(
		(rect) => ({ top: rect.bottom, left: rect.left }),
	);
	const { buttonRef: bellButtonRef, popoverRef: bellPopoverRef } = usePopoverAnchor(
		(rect) => {
			// Keep the panel (CSS width: min(22rem, 100vw - 2rem)) inside the viewport
			// even when the bell sits far from the right edge.
			// `right` on a fixed element is measured from the viewport without the
			// scrollbar, which window.innerWidth includes, so use clientWidth.
			const viewportWidth = document.documentElement.clientWidth;
			const width = Math.min(22 * 16, viewportWidth - 32);
			const bellCenterFromRight = viewportWidth - (rect.left + rect.width / 2);
			// The triangle is 24px wide and sits inside the panel's 1px border. Put
			// the panel's edge so the triangle's tip is under the bell's center with
			// the usual 10px inset, then clamp the panel into the viewport.
			const panelRight = Math.max(
				16,
				Math.min(bellCenterFromRight - 10 - 1 - 12, viewportWidth - 16 - width),
			);
			return {
				top: rect.bottom + 4,
				right: panelRight,
				arrowRight: Math.max(10, bellCenterFromRight - panelRight - 1 - 12),
			};
		},
	);
	const { buttonRef: userButtonRef, popoverRef: userPopoverRef } = usePopoverAnchor(
		(rect) => ({ top: rect.bottom + 12, right: window.innerWidth - rect.right }),
	);

	const navigate = useNavigate();
	const setToken = useAuthStore((state) => state.setToken);
	const queryClient = useQueryClient();
	const moderatorMode = useModeratorModeStore((state) => state.moderatorMode);
	const setModeratorMode = useModeratorModeStore((state) => state.setModeratorMode);
	const toggleModeratorMode = () => {
		setModeratorMode(!moderatorMode);
		queryClient.resetQueries();
	};
	const logout = () => {
		setToken(null);
		queryClient.removeQueries({ queryKey: ["me"] });
		navigate({ to: "/" });
	};

	return (
		<header
			id={styles["site-header"]}
			className={clsx("page-wrap", location.pathname === "/" ? styles.landing : "")}
		>
			<div>
				<Link className={styles["header-logo"]} to="/">
					<img
						src={`/images/${logo_path}${theme === "dark" ? "_dark" : ""}.png`}
						alt="Gamers' Plane Logo"
					/>
				</Link>
				<nav>
					<ul>
						<li className={styles["has-dropdown"]}>
							<button type="button" ref={toolsButtonRef} popoverTarget="tools-menu">
								Tools
							</button>
							{/* biome-ignore lint/a11y/useKeyWithClickEvents: delegated click handler catches bubbled clicks from interactive <a> children, which already fire click on keyboard activation */}
							<ul
								id="tools-menu"
								className={styles.dropdown}
								popover="auto"
								ref={toolsPopoverRef}
								onClick={(e) => {
									if (e.target instanceof HTMLElement) {
										e.currentTarget.hidePopover();
									}
								}}
							>
								<li>
									<Link to="/tools/dice">Dice</Link>
								</li>
								<li>
									<Link to="/tools/cards">Cards</Link>
								</li>
							</ul>
						</li>
						<li>
							<Link to="/systems">Systems</Link>
						</li>
						{me && (
							<li>
								<Link to="/characters">Characters</Link>
							</li>
						)}
						<li>
							<Link to="/games">Games</Link>
						</li>
						<li>
							<Link to="/forums/{-$forumId}" params={{ forumId: 0 }}>
								Forums
							</Link>
						</li>
						{me ? (
							<>
								<li className={styles["header-bell"]}>
									<button
										type="button"
										ref={bellButtonRef}
										popoverTarget="header_notifications"
										aria-label={
											notificationCount > 0
												? `Notifications (${notificationCount})`
												: "Notifications"
										}
									>
										<svg
											viewBox="0 0 24 24"
											width="1.2em"
											height="1.2em"
											fill="currentColor"
											stroke="currentColor"
											strokeWidth="2"
											strokeLinecap="round"
											strokeLinejoin="round"
											aria-hidden="true"
										>
											<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
											<path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" />
										</svg>
										{notificationCount > 0 && (
											<span className={styles["bell-badge"]}>{notificationCount}</span>
										)}
									</button>
									{/* biome-ignore lint/a11y/useKeyWithClickEvents: delegated click handler catches bubbled clicks from interactive <a> children, which already fire click on keyboard activation */}
									<ul
										id="header_notifications"
										className={styles["dropdown"]}
										popover="auto"
										ref={bellPopoverRef}
										onClick={(e) => {
											if (e.target instanceof HTMLElement) {
												e.currentTarget.hidePopover();
											}
										}}
									>
										{notificationCount === 0 && (
											<li className={styles["notification-empty"]}>
												Nothing needs your attention.
											</li>
										)}
										{shownNotifications.map((item) => (
											<li key={item.key}>
												<Link to="/games/$gameId" params={{ gameId: item.gameId }}>
													{item.text}
												</Link>
											</li>
										))}
										{hasMoreNotifications && (
											<li>
												<Link to="/notifications">View all ({notificationCount})</Link>
											</li>
										)}
									</ul>
								</li>

								<li className={styles["header-avatar"]}>
									<button
										type="button"
										ref={userButtonRef}
										popoverTarget="header_user-menu"
									>
										<img src={me.avatar} alt={me.username} />
										{pmCount > 0 && (
											<img
												className={styles["header-new-messages"]}
												src="/images/icons/envelope.jpg"
												alt="New Messages"
											/>
										)}
									</button>
									{/* biome-ignore lint/a11y/useKeyWithClickEvents: delegated click handler catches bubbled clicks from interactive <a>/<button> children, which already fire click on keyboard activation */}
									<ul
										id="header_user-menu"
										className={styles.dropdown}
										popover="auto"
										ref={userPopoverRef}
										onClick={(e) => {
											if (
												e.target instanceof HTMLElement &&
												!e.target.closest(".theme-toggle")
											) {
												e.currentTarget.hidePopover();
											}
										}}
									>
										<li>
											<Link to="/profile">Edit Profile</Link>
										</li>
										<li>
											<Link to="/pms">
												Messages{pmCount > 0 ? ` (${pmCount})` : ""}
											</Link>
										</li>
										{me.gameModerate && (
											<li>
												<button
													type="button"
													className="non-button"
													onClick={toggleModeratorMode}
												>
													{moderatorMode
														? "Switch to player mode"
														: "Switch to moderator mode"}
												</button>
											</li>
										)}
										<li>
											<ThemeToggle showLabel />
										</li>
										<li>
											<button type="button" className="non-button" onClick={logout}>
												Logout
											</button>
										</li>
									</ul>
								</li>
							</>
						) : (
							<>
								<li className={styles["header-register"]}>
									<Link to="/register">Register</Link>
								</li>
								<li className={styles["header-login"]}>
									<Link to="/login" search={{ redirect: location.pathname }}>
										Login
									</Link>
								</li>
								<li className={styles["header-theme-toggle"]}>
									<ThemeToggle />
								</li>
							</>
						)}
					</ul>
				</nav>
			</div>
		</header>
	);
}
export default Header;
