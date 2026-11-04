import {
	FONT_FAMILIES,
	isFontFamilyKey,
} from "#/components/tiptap/tiptap-extension/font-family-extension";
import {
	FONT_SIZES,
	isFontSizeKey,
} from "#/components/tiptap/tiptap-extension/font-size-extension";
import { PresetDropdown } from "#/components/tiptap/tiptap-ui/preset-dropdown/preset-dropdown";

export function FontSizeDropdown() {
	return (
		<PresetDropdown
			ariaLabel="Font size"
			defaultLabel="Size"
			normalLabel="Default"
			options={FONT_SIZES}
			readActive={(editor) => {
				const size: unknown = editor.getAttributes("fontSize")["size"];
				return isFontSizeKey(size) ? size : null;
			}}
			onSelect={(editor, key) => {
				const chain = editor.chain().focus();
				if (isFontSizeKey(key)) chain.setFontSizePreset(key).run();
				else chain.unsetFontSizePreset().run();
			}}
		/>
	);
}

export function FontFamilyDropdown() {
	return (
		<PresetDropdown
			ariaLabel="Font"
			defaultLabel="Font"
			normalLabel="Default"
			options={FONT_FAMILIES}
			previewAttribute="data-font"
			readActive={(editor) => {
				const font: unknown = editor.getAttributes("fontFamily")["font"];
				return isFontFamilyKey(font) ? font : null;
			}}
			onSelect={(editor, key) => {
				const chain = editor.chain().focus();
				if (isFontFamilyKey(key)) chain.setFontFamilyPreset(key).run();
				else chain.unsetFontFamilyPreset().run();
			}}
		/>
	);
}
