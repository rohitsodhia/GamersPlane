import { Image } from "@tiptap/extension-image";
import {
	floatAttribute,
	isFloatKey,
} from "#/components/tiptap/tiptap-extension/float-attribute";

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		imageFloat: {
			/** Float the selected image left or right, or back to none. */
			setImageFloat: (float: "none" | "left" | "right") => ReturnType;
		};
	}
}

// The stock image plus a `float` attribute (key only, see float-attribute.ts).
export const FloatImage = Image.extend({
	addAttributes() {
		return {
			...this.parent?.(),
			float: floatAttribute,
		};
	},

	addCommands() {
		return {
			...this.parent?.(),
			setImageFloat:
				(float) =>
				({ commands }) =>
					isFloatKey(float) && commands.updateAttributes(this.name, { float }),
		};
	},
});
