import babel from "@rolldown/plugin-babel";
import { devtools } from "@tanstack/devtools-vite";

import { tanstackStart } from "@tanstack/react-start/plugin/vite";

import viteReact, { reactCompilerPreset } from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";
import { defineConfig } from "vite";

const config = defineConfig({
	envDir: "../",
	resolve: { tsconfigPaths: true },
	// The production build's output (hundreds of copied images) is never a source
	// file, and each file in it would take one of the system's limited file watchers.
	server: { watch: { ignored: ["**/.output/**"] } },
	plugins: [
		devtools(),
		nitro({ rollupConfig: { external: [/^@sentry\//] } }),
		tanstackStart({
			spa: {
				enabled: true,
			},
		}),
		viteReact(),
		babel({ presets: [reactCompilerPreset()] }),
	],
});

export default config;
