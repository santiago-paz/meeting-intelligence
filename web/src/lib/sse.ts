export type ServerEvent = { event: string; data: string };

/**
 * Reads a text/event-stream body as it arrives. EventSource cannot POST a
 * question, so fetch does and the parsing lives here: a block ends at a
 * blank line, `data:` lines join with newlines, comment lines are skipped,
 * and a final block the server never terminated still counts.
 */
export async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ServerEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const event = parseBlock(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        if (event) yield event;
      }
      if (done) break;
    }
    const last = parseBlock(buffer);
    if (last) yield last;
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): ServerEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length === 0 ? null : { event, data: data.join("\n") };
}
