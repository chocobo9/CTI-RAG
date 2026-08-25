import { type ProviderDispatchSecretBinder, piDigest } from "@earendil-works/pi-agent-core";
import {
	type Context,
	createModels,
	type FauxResponseStep,
	fauxAssistantMessage,
	type Message,
	type MutableModels,
} from "@earendil-works/pi-ai";

const exactCounterIdentity = {
	protocol: "pi-prepared-simple-exact-input-counter-identity/v1" as const,
	counterId: "workspace.task-understanding.exact-input",
	counterVersion: "v1",
	tokenizerId: "workspace.task-understanding.unconfigured",
	tokenizerVersion: "v1",
	wrapperPolicyId: "pi.prepared-simple",
	wrapperPolicyVersion: "v1",
};

export function createTaskUnderstandingModels(): MutableModels {
	return createModels({
		exactInputCounterResolver: {
			create: () => ({
				presence: "present",
				value: {
					identity: exactCounterIdentity,
					count: (request) => {
						if (request.minimumOutputProbe.presence !== "present") {
							return Promise.resolve({ kind: "invalid", code: "counter_input_invalid" });
						}
						return Promise.resolve({
							kind: "exact",
							count: {
								protocol: "pi-prepared-simple-exact-input-count/v1",
								logicalInvocationDigest: request.logicalInvocationDigest,
								modelDigest: request.modelDigest,
								counterBindingDigest: request.counterBindingDigest,
								counterIdentity: exactCounterIdentity,
								inputTokenCount: 1,
								minimumOutput: {
									presence: "present",
									value: {
										candidateTextDigest: request.minimumOutputProbe.value.candidateTextDigest,
										outputTokenCount: 1,
									},
								},
							},
						});
					},
					revalidate: () => Promise.resolve({ kind: "exact" }),
				},
			}),
		},
	});
}

export const providerDispatchSecretBinder: ProviderDispatchSecretBinder = {
	bind: ({ domain, fieldName, valueUtf8 }) =>
		Promise.resolve({
			protocol: "pi-provider-secret-binding/v1",
			algorithm: "HMAC-SHA-256",
			keyId: "workspace-test-provider-secret-key",
			domain,
			fieldName,
			utf8Length: valueUtf8.length,
			macBase64Url: "A".repeat(43),
		}),
};

function messageText(message: Message): string {
	if (message.role === "user") {
		if (typeof message.content === "string") return message.content;
		return message.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("");
	}
	if (message.role === "assistant") {
		return message.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("");
	}
	return "";
}

export function taskUnderstandingProposal(context: Context): string {
	const serialized = context.messages
		.map(messageText)
		.find((text) => text.includes('"protocol":"workspace-task-understanding-invocation/v1"'));
	if (!serialized) throw new Error("Task Understanding invocation was not provided");
	const invocation = JSON.parse(serialized) as { originalTask: { taskId: string; text: string } };
	const { taskId, text } = invocation.originalTask;
	return JSON.stringify({
		protocol: "workspace-task-understanding-proposal/v1",
		normalizedReading: text,
		corrections: [],
		intent: { kind: "case_analysis", sourceClaimRefs: ["task_claim"] },
		outcomes: [
			{
				proposalOutcomeId: "task_outcome",
				requestedOutcome: "summary",
				objective: text,
				sourceClaimRefs: ["task_claim"],
			},
		],
		ambiguities: [],
		sourceClaims: [
			{
				claimId: "task_claim",
				kind: "original_task_text_span",
				startUtf16: 0,
				endUtf16: text.length,
				textDigest: piDigest({
					protocol: "workspace-task-source-span-basis/v1",
					sourceKind: "original_user_task",
					taskId,
					startUtf16: 0,
					endUtf16: text.length,
					text,
				}),
			},
		],
	});
}

export function withTaskUnderstandingResponses(responses: readonly FauxResponseStep[]): FauxResponseStep[] {
	return responses.flatMap((response) => [
		(context: Context) => fauxAssistantMessage(taskUnderstandingProposal(context)),
		response,
	]);
}
