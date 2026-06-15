import { Link, useLocation } from "@tanstack/react-router";
import { useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { useThemeStore } from "@/store/theme";

function Header() {
	const location = useLocation();
	const theme = useThemeStore((state) => state.theme);

	const logo_path = location.pathname === "/" ? "header_logo" : "logo";

	const [toolsOpen, setToolsOpen] = useState<boolean>(false);

	return (
		<header className={`${location.pathname === "/" ? "landing" : ""}`}>
			<div className="page-wrap">
				<Link to="/">
					<img
						id="header_logo"
						src={`/images/${logo_path}${theme === "dark" ? "_dark" : ""}.png`}
						alt="Gamers' Plane Logo"
					/>
				</Link>
				<nav>
					<ul>
						<li className="has-dropdown">
							<button
								type="button"
								onClick={() => setToolsOpen((open) => !open)}
							>
								Tools
							</button>
							{toolsOpen && (
								<ul className="dropdown">
									<li>
										<Link to="/tools/dice">Dice</Link>
									</li>
									<li>
										<Link to="/tools/cards">Cards</Link>
									</li>
								</ul>
							)}
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
						<li id="header_register">
							<Link to="/register">Register</Link>
						</li>
						<li id="header_login">
							<Link to="/login">Login</Link>
						</li>
					</ul>
					<ThemeToggle />
				</nav>
			</div>
		</header>
	);
}
export default Header;
