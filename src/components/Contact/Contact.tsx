import ContactForm from "../ContactForm/ContactForm";
import Reveal from "../Reveal/Reveal";
import WhatsAppCard from "../WhatsAppCard/WhatsAppCard";
import styles from "./Contact.module.css";

export interface ContactProps {
  title?: string;
  lede?: string;
}

export default function Contact({
  title = "Talk to the studio",
  lede = "Sizing, cloth, lead times, or a piece you want cut differently — send it over and a person will answer.",
}: ContactProps) {
  return (
    <section className={styles.section} id="contact" data-section aria-labelledby="contact-title">
      <div className={styles.inner}>
        <Reveal className={styles.header}>
          <h2 className={styles.title} id="contact-title">
            {title}
          </h2>
          <p className={styles.lede}>{lede}</p>
        </Reveal>

        <div className={styles.columns}>
          <Reveal>
            <ContactForm />
          </Reveal>
          <Reveal delayMs={110}>
            <WhatsAppCard />
          </Reveal>
        </div>
      </div>
    </section>
  );
}
