import { Buffer } from "node:buffer";
import { createHmac, timingSafeEqual } from "node:crypto";
import { piDigest } from "@earendil-works/pi-agent-core";
import type { SessionReceiptAuthenticator, SessionReceiptAuthenticatorBinding } from "../types.ts";

class NodeHmacSessionReceiptAuthenticator implements SessionReceiptAuthenticator {
	readonly authenticatorId: string;
	readonly binding: SessionReceiptAuthenticatorBinding;
	private readonly key: Uint8Array;

	constructor(input: { authenticatorId: string; key: Uint8Array }) {
		if (!input.authenticatorId.trim() || input.key.byteLength < 32) {
			throw new Error("Invalid receipt authenticator configuration");
		}
		this.authenticatorId = input.authenticatorId;
		this.binding = Object.freeze({
			authenticatorId: input.authenticatorId,
			algorithm: "hmac-sha256",
			keyId: input.authenticatorId,
			policyRevision: 1,
			verificationPolicyDigest: piDigest({
				protocol: "workspace-session-receipt-verification-policy/v1",
				authenticatorId: input.authenticatorId,
				algorithm: "hmac-sha256",
			}),
		});
		this.key = new Uint8Array(input.key);
	}

	async sign(payload: string): Promise<string> {
		return createHmac("sha256", this.key).update(payload).digest("hex");
	}

	async verify(payload: string, signature: string): Promise<boolean> {
		if (!/^[0-9a-f]{64}$/.test(signature)) return false;
		const expected = await this.sign(payload);
		return timingSafeEqual(Buffer.from(expected, "hex"), Buffer.from(signature, "hex"));
	}
}

export function createNodeHmacSessionReceiptAuthenticator(input: {
	authenticatorId: string;
	key: Uint8Array;
}): SessionReceiptAuthenticator {
	return new NodeHmacSessionReceiptAuthenticator(input);
}
