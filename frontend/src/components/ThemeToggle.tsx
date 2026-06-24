import { useEffect, useState } from "react";

import { useThemeStore } from "#/store/theme";

type ThemeMode = "light" | "dark" | "auto";

function LightDarkIcon({ current }: { current: ThemeMode }) {
	return (
		<svg
			version="1.2"
			baseProfile="tiny"
			xmlns="http://www.w3.org/2000/svg"
			xmlnsXlink="http://www.w3.org/1999/xlink"
			x="0px"
			y="0px"
			width="30px"
			height="30px"
			viewBox="0 0 30 30"
			xmlSpace="preserve"
			className={`theme-toggle-icon-${current}`}
		>
			<title>{`Light/Dark mode icon - Currently ${current}`}</title>
			<g className="light-layer">
				<g>
					<path
						id="theme-toggle-icon-layer-light"
						fill="#FFFFFF"
						d="M15,26C8.935,26,4,21.065,4,15S8.935,4,15,4s11,4.935,11,11S21.065,26,15,26z"
					/>
					<path
						d="M15,5c5.514,0,10,4.486,10,10c0,5.514-4.486,10-10,10C9.486,25,5,20.514,5,15C5,9.486,9.486,5,15,5 M15,3
			C8.372,3,3,8.372,3,15c0,6.627,5.372,12,12,12c6.627,0,12-5.373,12-12C27,8.372,21.627,3,15,3L15,3z"
					/>
				</g>
			</g>
			<g className="dark-layer">
				<g>
					<path
						d="M15,26.5C8.659,26.5,3.5,21.341,3.5,15c0-4.843,3.004-9.101,7.448-10.766C9.954,6.058,9.434,8.096,9.434,10.2
			c0,6.893,5.606,12.501,12.498,12.501c0.573,0,1.146-0.039,1.712-0.118C21.47,25.057,18.325,26.5,15,26.5z"
					/>
					<path
						d="M15,26.5C8.659,26.5,3.5,21.341,3.5,15c0-4.843,3.004-9.101,7.448-10.766C9.954,6.058,9.434,8.096,9.434,10.2
			c0,6.893,5.606,12.501,12.498,12.501c0.573,0,1.146-0.039,1.712-0.118C21.47,25.057,18.325,26.5,15,26.5z"
					/>
				</g>
			</g>
		</svg>
	);
}

function getInitialMode(): ThemeMode {
	if (typeof window === "undefined") {
		return "auto";
	}

	const stored = window.localStorage.getItem("theme");
	if (stored === "light" || stored === "dark" || stored === "auto") {
		return stored;
	}

	return "auto";
}

function applyThemeMode(mode: ThemeMode, setTheme: (theme: ThemeMode) => void) {
	const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
	const resolved = mode === "auto" ? (prefersDark ? "dark" : "light") : mode;

	document.documentElement.classList.remove("light", "dark");
	document.documentElement.classList.add(resolved);

	if (mode === "auto") {
		document.documentElement.removeAttribute("data-theme");
	} else {
		document.documentElement.setAttribute("data-theme", mode);
	}

	document.documentElement.style.colorScheme = resolved;
	setTheme(resolved);
}

export default function ThemeToggle() {
	const [mode, setMode] = useState<ThemeMode>("auto");
	const setTheme = useThemeStore((state) => state.setToken);

	useEffect(() => {
		const initialMode = getInitialMode();
		setMode(initialMode);
		applyThemeMode(initialMode, setTheme);
	}, [setTheme]);

	useEffect(() => {
		if (mode !== "auto") {
			return;
		}

		const media = window.matchMedia("(prefers-color-scheme: dark)");
		const onChange = () => applyThemeMode("auto", setTheme);

		media.addEventListener("change", onChange);
		return () => {
			media.removeEventListener("change", onChange);
		};
	}, [mode, setTheme]);

	function toggleMode() {
		const nextMode: ThemeMode =
			mode === "light" ? "dark" : mode === "dark" ? "auto" : "light";
		setMode(nextMode);
		applyThemeMode(nextMode, setTheme);
		window.localStorage.setItem("theme", nextMode);
	}

	const label =
		mode === "auto"
			? "Theme mode: auto (system). Click to switch to light mode."
			: `Theme mode: ${mode}. Click to switch mode.`;

	return (
		<button
			type="button"
			onClick={toggleMode}
			aria-label={label}
			title={label}
			className="theme-toggle"
		>
			{/* {mode === "auto" ? "Auto" : mode === "dark" ? "Dark" : "Light"} */}
			<LightDarkIcon current={mode} />
		</button>
	);
}
