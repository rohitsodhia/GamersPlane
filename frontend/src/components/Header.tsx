import { Link, useLocation } from "@tanstack/react-router";
import ThemeToggle from "@/components/ThemeToggle";

function Header() {
	const location = useLocation();
	const logo_path = location.pathname === "/" ? "header_logo.png" : "logo.png";

	return (
		<header className={`${location.pathname === "/" ? "landing" : ""}`}>
			<div className="page-wrap">
			</div>
		</header>
	);
}
export default Header;
