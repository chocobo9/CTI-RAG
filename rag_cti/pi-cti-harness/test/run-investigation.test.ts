import type { AgentTool } from "@earendil-works/pi-agent-core";
import {
  fauxAssistantMessage,
  fauxToolCall,
  registerFauxProvider,
} from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { afterEach, describe, expect, it } from "vitest";

import {
  type InvestigationLifecycleEvent,
  runInvestigation,
} from "../src/index.js";

describe("runInvestigation", () => {
  const registrations: Array<{ unregister(): void }> = [];

  afterEach(() => {
    for (const registration of registrations.splice(0)) {
      registration.unregister();
    }
  });

  it("runs one CTI capability through Pi and returns the final completion", async () => {
    const provider = registerFauxProvider();
    registrations.push(provider);

    const invocations: string[] = [];
    const parameters = Type.Object({ indicator: Type.String() });
    const capability: AgentTool<typeof parameters, { indicator: string }> = {
      name: "lookup_indicator",
      label: "Lookup indicator",
      description: "Look up one indicator in the stable CTI data service.",
      parameters,
      async execute(_toolCallId, { indicator }) {
        invocations.push(indicator);
        return {
          content: [{ type: "text", text: "APT29 is linked to example.org" }],
          details: { indicator },
        };
      },
    };

    provider.setResponses([
      fauxAssistantMessage(
        fauxToolCall("lookup_indicator", { indicator: "example.org" }, { id: "call-1" }),
        { stopReason: "toolUse" },
      ),
      (context) => {
        expect(context.messages.at(-1)).toMatchObject({
          role: "toolResult",
          toolCallId: "call-1",
          toolName: "lookup_indicator",
          isError: false,
          content: [{ type: "text", text: "APT29 is linked to example.org" }],
        });
        return fauxAssistantMessage("The available CTI links example.org to APT29.");
      },
    ]);

    const result = await runInvestigation({
      prompt: "Investigate example.org",
      systemPrompt: "Investigate with the registered CTI capability.",
      model: provider.getModel(),
      capability,
      isComplete: ({ message }) =>
        message.content.some(
          (content) => content.type === "text" && content.text.includes("APT29"),
        ),
    });

    expect(invocations).toEqual(["example.org"]);
    expect(provider.state.callCount).toBe(2);
    expect(result.outcome).toBe("complete");
    expect(result.finalMessage.content).toEqual([
      { type: "text", text: "The available CTI links example.org to APT29." },
    ]);
  });

  it("honors the CTI completion policy through Pi's post-turn stop hook", async () => {
    const provider = registerFauxProvider();
    registrations.push(provider);

    const parameters = Type.Object({ indicator: Type.String() });
    const capability: AgentTool<typeof parameters, undefined> = {
      name: "lookup_indicator",
      label: "Lookup indicator",
      description: "Look up one indicator.",
      parameters,
      async execute() {
        return {
          content: [{ type: "text", text: "enough evidence" }],
          details: undefined,
        };
      },
    };
    provider.setResponses([
      fauxAssistantMessage(
        fauxToolCall("lookup_indicator", { indicator: "example.org" }),
        { stopReason: "toolUse" },
      ),
    ]);

    const result = await runInvestigation({
      prompt: "Investigate example.org",
      systemPrompt: "Use the capability.",
      model: provider.getModel(),
      capability,
      isComplete: ({ toolResults }) => toolResults.length === 1,
    });

    expect(provider.state.callCount).toBe(1);
    expect(result.outcome).toBe("complete");
    expect(result.finalMessage.stopReason).toBe("toolUse");
  });

  it("does not treat a no-tool assistant response as CTI success", async () => {
    const provider = registerFauxProvider();
    registrations.push(provider);

    const capability: AgentTool = {
      name: "lookup_indicator",
      label: "Lookup indicator",
      description: "Look up one indicator.",
      parameters: Type.Object({}),
      async execute() {
        return { content: [], details: undefined };
      },
    };
    provider.setResponses([
      fauxAssistantMessage("I think the investigation is finished."),
    ]);

    const result = await runInvestigation({
      prompt: "Investigate example.org",
      systemPrompt: "Use the capability.",
      model: provider.getModel(),
      capability,
      isComplete: () => false,
    });

    expect(result.outcome).toBe("incomplete");
  });

  it("represents provider failures as Pi assistant errors", async () => {
    const provider = registerFauxProvider();
    registrations.push(provider);

    const capability: AgentTool = {
      name: "lookup_indicator",
      label: "Lookup indicator",
      description: "Look up one indicator.",
      parameters: Type.Object({}),
      async execute() {
        return { content: [], details: undefined };
      },
    };
    provider.setResponses([
      () => {
        throw new Error("provider unavailable");
      },
    ]);

    const result = await runInvestigation({
      prompt: "Investigate example.org",
      systemPrompt: "Use the capability.",
      model: provider.getModel(),
      capability,
      isComplete: () => false,
    });

    expect(result.outcome).toBe("error");
    expect(result.finalMessage).toMatchObject({
      role: "assistant",
      stopReason: "error",
      errorMessage: "provider unavailable",
    });
  });

  it("returns tool failures to Pi and exposes the selected native lifecycle event", async () => {
    const provider = registerFauxProvider();
    registrations.push(provider);

    const parameters = Type.Object({ indicator: Type.String() });
    const capability: AgentTool<typeof parameters> = {
      name: "lookup_indicator",
      label: "Lookup indicator",
      description: "Look up one indicator.",
      parameters,
      async execute() {
        throw new Error("lookup failed");
      },
    };
    provider.setResponses([
      fauxAssistantMessage(
        fauxToolCall("lookup_indicator", { indicator: "example.org" }, { id: "call-1" }),
        { stopReason: "toolUse" },
      ),
      (context) => {
        expect(context.messages.at(-1)).toMatchObject({
          role: "toolResult",
          toolCallId: "call-1",
          isError: true,
          content: [{ type: "text", text: "lookup failed" }],
        });
        return fauxAssistantMessage("The lookup failed; no CTI conclusion is available.");
      },
    ]);
    const events: InvestigationLifecycleEvent[] = [];

    const result = await runInvestigation({
      prompt: "Investigate example.org",
      systemPrompt: "Use the capability.",
      model: provider.getModel(),
      capability,
      isComplete: ({ message }) => message.stopReason === "stop",
      onEvent: (event) => {
        events.push(event);
      },
    });

    expect(result.outcome).toBe("complete");
    expect(events).toContainEqual(
      expect.objectContaining({
        type: "tool_execution_end",
        toolName: "lookup_indicator",
        isError: true,
      }),
    );
  });

  it("represents an abort through Pi's native aborted assistant message", async () => {
    const provider = registerFauxProvider();
    registrations.push(provider);

    const capability: AgentTool = {
      name: "lookup_indicator",
      label: "Lookup indicator",
      description: "Look up one indicator.",
      parameters: Type.Object({}),
      async execute() {
        return { content: [], details: undefined };
      },
    };
    let markResponseStarted: () => void = () => undefined;
    const responseStarted = new Promise<void>((resolve) => {
      markResponseStarted = resolve;
    });
    provider.setResponses([
      async (_context, options) => {
        markResponseStarted();
        await new Promise<void>((resolve) => {
          options?.signal?.addEventListener("abort", () => resolve(), { once: true });
        });
        return fauxAssistantMessage("This response must be aborted.");
      },
    ]);
    const abortController = new AbortController();

    const pendingResult = runInvestigation({
      prompt: "Investigate example.org",
      systemPrompt: "Use the capability.",
      model: provider.getModel(),
      capability,
      isComplete: () => false,
      signal: abortController.signal,
    });
    await responseStarted;
    abortController.abort();
    const result = await pendingResult;

    expect(result.outcome).toBe("aborted");
    expect(result.finalMessage).toMatchObject({
      role: "assistant",
      stopReason: "aborted",
      errorMessage: "Request was aborted",
    });
  });
});
