import type { ChatModel, Message } from "./api";

/** Put each published model after the last assistant response in its user turn.
 * Tool output can be thousands of pixels above the final answer in a long build. */
export function placeChatModels(messages: Message[], models: Record<string, ChatModel>) {
  const byMessage = new Map<number, ChatModel[]>();
  const assigned = new Set<string>();
  let turnModels = new Set<string>();
  let lastAssistant: number | undefined;
  function finishTurn() {
    if (lastAssistant !== undefined) {
      const cards = [...turnModels].filter(id => models[id] && !assigned.has(id)).map(id => models[id]);
      if (cards.length) byMessage.set(lastAssistant, cards);
      cards.forEach(m => assigned.add(m.id));
    }
    turnModels = new Set();
    lastAssistant = undefined;
  }
  for (const message of messages) {
    if (message.role === "user" && !message._hidden && !message._ui_only) finishTurn();
    if (message.role === "assistant" && !message._hidden && !message._ui_only) lastAssistant = message.id;
    (message._models ?? []).forEach(id => turnModels.add(id));
  }
  finishTurn();
  return { byMessage, unplaced: Object.values(models).filter(m => !assigned.has(m.id)) };
}
