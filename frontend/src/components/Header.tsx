import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import ThemeToggle from "#/components/ThemeToggle";
import { meQueryOptions } from "#/queries/me";
import { useAuthStore } from "#/stores/auth";
import { useThemeStore } from "#/stores/theme";

type PopoverPosition = { top: number; left?: number; right?: number };

function usePopoverAnchor(position: (rect: DOMRect) => PopoverPosition) {
	const buttonRef = useRef<HTMLButtonElement>(null);
	const positionRef = useRef(position);
	positionRef.current = position;

	const popoverRef = useCallback((popover: HTMLUListElement | null) => {
		if (!popover || !buttonRef.current) return;
		const button = buttonRef.current;
		function onToggle(e: ToggleEvent) {
			if (e.newState === "open") {
				const rect = button.getBoundingClientRect();
				const pos = positionRef.current(rect);
				popover.style.top = `${pos.top}px`;
				if (pos.left !== undefined) popover.style.left = `${pos.left}px`;
				if (pos.right !== undefined) popover.style.right = `${pos.right}px`;
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

	const { buttonRef: toolsButtonRef, popoverRef: toolsPopoverRef } = usePopoverAnchor(
		(rect) => ({ top: rect.bottom, left: rect.left }),
	);
	const { buttonRef: userButtonRef, popoverRef: userPopoverRef } = usePopoverAnchor(
		(rect) => ({ top: rect.bottom + 12, right: window.innerWidth - rect.right }),
	);

	const navigate = useNavigate();
	const setToken = useAuthStore((state) => state.setToken);
	const queryClient = useQueryClient();
	const logout = () => {
		setToken(null);
		queryClient.removeQueries({ queryKey: ["me"] });
		navigate({ to: "/" });
	};

	return (
		<header className={`${location.pathname === "/" ? "landing" : ""}`}>
			<div className="page-wrap">
				<Link id="header_logo" to="/">
					<img
						src={`/images/${logo_path}${theme === "dark" ? "_dark" : ""}.png`}
						alt="Gamers' Plane Logo"
					/>
				</Link>
				<nav>
					<ul>
						<li className="has-dropdown">
							<button type="button" ref={toolsButtonRef} popoverTarget="tools-menu">
								Tools
							</button>
							<ul
								id="tools-menu"
								className="dropdown"
								popover="auto"
								ref={toolsPopoverRef}
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
						<li>
							<Link to="/games">Games</Link>
						</li>
						<li>
							<Link to="/forums">Forums</Link>
						</li>
						{me ? (
							<li id="header_avatar">
								<button
									type="button"
									ref={userButtonRef}
									popoverTarget="header_user_menu"
								>
									<img src={me.avatar} alt={me.username} />
								</button>
								<ul
									id="header_user_menu"
									className="dropdown"
									popover="auto"
									ref={userPopoverRef}
								>
									<li>
										<Link to="/profile">Edit Profile</Link>
									</li>
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
						) : (
							<>
								<li id="header_register">
									<Link to="/register">Register</Link>
								</li>
								<li id="header_login">
									<Link to="/login" search={{ redirect: location.pathname }}>
										Login
									</Link>
								</li>
								<li id="header_theme_toggle">
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
