import { Link, useLocation } from "@tanstack/react-router";
import ThemeToggle from "@/components/ThemeToggle";

function Header() {
	const location = useLocation();
	const logo_path = location.pathname === "/" ? "header_logo.png" : "logo.png";

	return (
		<header className={`${location.pathname === "/" ? "landing" : ""}`}>
			<div className="page-wrap">
				<Link to="/">
					<img
						id="header_logo"
						src={`/images/${logo_path}`}
						alt="Gamers' Plane Logo"
					/>
				</Link>
				<nav>
					<ul>
						<li>
							<Link to="/tools">Tools</Link>
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
						<li>
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
