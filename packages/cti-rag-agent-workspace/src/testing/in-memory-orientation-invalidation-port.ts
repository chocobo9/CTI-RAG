import type { OrientationInvalidation, OrientationInvalidationPort } from "../types.ts";

export class InMemoryOrientationInvalidationPort implements OrientationInvalidationPort {
	private readonly subscriptions = new Set<{
		caseRef: string;
		principalRef: string;
		listener: (invalidation: OrientationInvalidation) => void;
	}>();

	subscribe(
		input: { caseRef: string; principalRef: string },
		listener: (invalidation: OrientationInvalidation) => void,
	): () => void {
		const subscription = { ...input, listener };
		this.subscriptions.add(subscription);
		return () => this.subscriptions.delete(subscription);
	}

	emit(invalidation: OrientationInvalidation): void {
		for (const subscription of this.subscriptions) {
			if (subscription.caseRef === invalidation.caseRef && subscription.principalRef === invalidation.principalRef) {
				subscription.listener(invalidation);
			}
		}
	}
}
