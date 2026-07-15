import {
  agentLoop,
  type AgentEvent,
  type AgentLoopConfig,
  type AgentMessage,
  type AgentTool,
} from "@earendil-works/pi-agent-core";
import type { AssistantMessage, Message, Model } from "@earendil-works/pi-ai";

export type CompletionPolicy = NonNullable<AgentLoopConfig["shouldStopAfterTurn"]>;

export type InvestigationLifecycleEvent = Extract<
  AgentEvent,
  { type: "turn_end" | "tool_execution_start" | "tool_execution_end" }
>;

export interface RunInvestigationOptions {
  prompt: string;
  systemPrompt: string;
  model: Model<any>;
  capability: AgentTool;
  isComplete: CompletionPolicy;
  signal?: AbortSignal;
  onEvent?: (event: InvestigationLifecycleEvent) => void | Promise<void>;
}

export interface InvestigationResult {
  outcome: "complete" | "incomplete" | "error" | "aborted";
  finalMessage: AssistantMessage;
  messages: AgentMessage[];
}

/** Run one headless CTI investigation using Pi's native agent loop. */
export async function runInvestigation(
  options: RunInvestigationOptions,
): Promise<InvestigationResult> {
  let completedByPolicy = false;
  let finalMessage: AssistantMessage | undefined;

  const stream = agentLoop(
    [
      {
        role: "user",
        content: options.prompt,
        timestamp: Date.now(),
      },
    ],
    {
      systemPrompt: options.systemPrompt,
      messages: [],
      tools: [options.capability],
    },
    {
      model: options.model,
      convertToLlm: (messages) => messages as Message[],
      shouldStopAfterTurn: async (context) => {
        const complete = await options.isComplete(context);
        completedByPolicy ||= complete;
        return complete;
      },
    },
    options.signal,
  );

  for await (const event of stream) {
    if (event.type === "turn_end" && event.message.role === "assistant") {
      finalMessage = event.message;
      await options.onEvent?.(event);
    } else if (
      event.type === "tool_execution_start" ||
      event.type === "tool_execution_end"
    ) {
      await options.onEvent?.(event);
    }
  }

  const messages = await stream.result();
  if (!finalMessage) {
    throw new Error("Pi ended the investigation without an assistant message");
  }

  const outcome =
    finalMessage.stopReason === "error"
      ? "error"
      : finalMessage.stopReason === "aborted"
        ? "aborted"
        : completedByPolicy
          ? "complete"
          : "incomplete";

  return { outcome, finalMessage, messages };
}
