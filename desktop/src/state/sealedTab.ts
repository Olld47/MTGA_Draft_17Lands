/** True when an event type marks a Sealed variant. Mirrors the backend's
 *  substring check (`LIMITED_TYPE_STRING_SEALED in event_type` in
 *  snapshot.py) so both "Sealed" and "TradSealed" count. */
export function isSealedEvent(eventType: string | null | undefined): boolean {
  return Boolean(eventType && eventType.includes("Sealed"));
}
