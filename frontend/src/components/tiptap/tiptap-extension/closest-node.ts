import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import type { EditorState } from "@tiptap/pm/state";

export type FoundNode = { pos: number; node: ProseMirrorNode };

/**
 * The innermost node called `name` that the selection is inside of (or that is itself
 * node-selected), with its document position. Used to unwrap or retarget the one
 * container the caret is in, rather than every container the selection touches.
 */
export function closestNode(state: EditorState, name: string): FoundNode | null {
	const { selection } = state;
	const selected = "node" in selection ? (selection.node as ProseMirrorNode) : null;
	if (selected?.type.name === name) return { pos: selection.from, node: selected };
	for (let depth = selection.$from.depth; depth > 0; depth--) {
		const node = selection.$from.node(depth);
		if (node.type.name === name) return { pos: selection.$from.before(depth), node };
	}
	return null;
}
