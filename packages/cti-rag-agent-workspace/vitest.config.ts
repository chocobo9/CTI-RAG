import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const agentSrcIndex = fileURLToPath(new URL("../agent/src/index.ts", import.meta.url));
const agentSrcNode = fileURLToPath(new URL("../agent/src/node.ts", import.meta.url));
const aiSrcIndex = fileURLToPath(new URL("../ai/src/index.ts", import.meta.url));
const aiSrcCompat = fileURLToPath(new URL("../ai/src/compat.ts", import.meta.url));
const workspaceSrcIndex = fileURLToPath(new URL("./src/index.ts", import.meta.url));
const workspaceSrcNode = fileURLToPath(new URL("./src/node.ts", import.meta.url));
const workspaceTestingIndex = fileURLToPath(new URL("./src/testing/index.ts", import.meta.url));

export default defineConfig({
	test: {
		environment: "node",
		reporters: "dot",
	},
	resolve: {
		alias: [
			{ find: /^@earendil-works\/pi-cti-rag-agent-workspace$/, replacement: workspaceSrcIndex },
			{ find: /^@earendil-works\/pi-cti-rag-agent-workspace\/node$/, replacement: workspaceSrcNode },
			{ find: /^@earendil-works\/pi-cti-rag-agent-workspace\/testing$/, replacement: workspaceTestingIndex },
			{ find: /^@earendil-works\/pi-agent-core$/, replacement: agentSrcIndex },
			{ find: /^@earendil-works\/pi-agent-core\/node$/, replacement: agentSrcNode },
			{ find: /^@earendil-works\/pi-ai$/, replacement: aiSrcIndex },
			{ find: /^@earendil-works\/pi-ai\/compat$/, replacement: aiSrcCompat },
		],
	},
});
