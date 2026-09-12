import Nav from "./components/Nav/Nav";
import Hero from "./components/Hero/Hero";
import Marquee from "./components/Marquee/Marquee";
import Collection from "./components/Collection/Collection";
import Story from "./components/Story/Story";
import Contact from "./components/Contact/Contact";
import Footer from "./components/Footer/Footer";
import WhatsAppFab from "./components/WhatsAppFab/WhatsAppFab";
import { config } from "./config";

/**
 * Black House — single-page brand and lead-generation site.
 * Section order is fixed: Nav → Hero → Marquee → Collection → Story →
 * Contact → Footer, with the WhatsApp FAB floating above everything.
 */
export default function App() {
  return (
    <>
      <a className="skip-link" href="#collection">
        Skip to the collection
      </a>

      <Nav />

      <main>
        <Hero />
        <Marquee />
        <Collection />
        <Story />
        <Contact />
      </main>

      <Footer />
      <WhatsAppFab message={`Hello ${config.brandName} — I have a question from the website.`} />
    </>
  );
}
