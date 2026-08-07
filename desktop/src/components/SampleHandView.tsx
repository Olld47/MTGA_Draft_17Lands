import type { SampleHand } from "../api/types";
import { artUrl } from "./cardColumns";

/** The 7-card sample draw as a stacked fan of Scryfall art. Legacy
 *  custom_deck.py rendered a card-image fan; both the Custom Deck and Suggest
 *  pages share it here. */
export function SampleHandView({ hand }: { hand: SampleHand }) {
  if (hand.message) {
    return <div className="empty-inline">{hand.message}</div>;
  }
  return (
    <div className="hand-fan">
      {hand.cards.map((c, i) => {
        const url = artUrl(c.image);
        return (
          <figure key={`${c.name}-${i}`} className="hand-card">
            {url ? <img src={url} alt={c.name} loading="lazy" /> : null}
            <figcaption>{c.name}</figcaption>
          </figure>
        );
      })}
    </div>
  );
}
