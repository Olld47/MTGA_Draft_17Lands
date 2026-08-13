/** True when an event type marks a Sealed variant. The bridge normalizes every
 *  Sealed event type to exactly "Sealed" or "TradSealed" (see
 *  src/constants.py LIMITED_TYPE_LIST / LIMITED_TYPES_DICT and the
 *  log_scanner.py normalization), so this matches by exact membership rather
 *  than substring. It is deliberately stricter than snapshot.py's
 *  LIMITED_TYPE_STRING_SEALED in event_type check, which would also accept a
 *  hypothetical future event type merely containing "Sealed". */
const SEALED_EVENT_TYPES = new Set(["Sealed", "TradSealed"]);

export function isSealedEvent(eventType: string | null | undefined): boolean {
  return typeof eventType === "string" && SEALED_EVENT_TYPES.has(eventType);
}
