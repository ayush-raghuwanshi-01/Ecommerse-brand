import GarmentArt from "../GarmentArt/GarmentArt";
import Reveal from "../Reveal/Reveal";
import { formatPrice, products } from "../../data/products";
import { getProductEnquiryLink } from "../../config";
import { WhatsAppGlyph } from "../WhatsAppGlyph/WhatsAppGlyph";
import type { Product } from "../../types";
import styles from "./Collection.module.css";

export interface CollectionProps {
  items?: Product[];
  title?: string;
  note?: string;
}

const silhouetteLabels: Record<Product["silhouette"], string> = {
  bomber: "Line drawing of a bomber jacket",
  trench: "Line drawing of a long trench coat",
  hoodie: "Line drawing of a hoodie",
  overshirt: "Line drawing of an overshirt",
  parka: "Line drawing of a hooded parka",
  vest: "Line drawing of a utility vest",
};

export default function Collection({
  items = products,
  title = "The collection",
  note = "Six pieces from the current run. Cloth is bought in fixed lots, so when a size sells through we do not cut it again.",
}: CollectionProps) {
  return (
    <section className={styles.section} id="collection" data-section aria-labelledby="collection-title">
      <Reveal className={styles.header}>
        <h2 className={styles.title} id="collection-title">
          {title}
        </h2>
        <p className={styles.note}>{note}</p>
      </Reveal>

      <Reveal delayMs={90} className={styles.railWrap}>
        <div
          className={styles.rail}
          role="region"
          aria-label="Collection gallery, scroll horizontally"
          tabIndex={0}
        >
          {items.map((product) => (
            <article className={styles.card} key={product.id}>
              <div className={styles.artPanel}>
                {product.tag ? <span className={styles.tag}>{product.tag}</span> : null}
                <GarmentArt
                  className={styles.art}
                  silhouette={product.silhouette}
                  label={silhouetteLabels[product.silhouette]}
                />
                <span className={styles.illustrative}>Illustrative</span>
              </div>

              <div className={styles.body}>
                <div className={styles.row}>
                  <h3 className={styles.name}>{product.name}</h3>
                  <span className={styles.price}>{formatPrice(product.price)}</span>
                </div>
                <span className={styles.ref}>{product.id}</span>

                <a
                  className={styles.enquire}
                  href={getProductEnquiryLink(product.name)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Enquire on WhatsApp
                  <WhatsAppGlyph className={styles.enquireIcon} />
                </a>
              </div>
            </article>
          ))}
        </div>
      </Reveal>

      <p className={styles.footnote}>
        Drawings are placeholders until the run is photographed. Sizes, cloth weights and
        lead times are confirmed in the chat.
      </p>
    </section>
  );
}
