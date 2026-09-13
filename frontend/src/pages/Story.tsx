import { Reveal, Seo } from '../components/bits';

export default function StoryPage() {
  return (
    <main className="page story-page">
      <Seo title="Our story — Black House" description="Small-batch outerwear from Bhopal. Slow made, built to stay." />
      <Reveal>
        <p className="eyebrow">The house</p>
        <h1>
          Slow made in <em>Bhopal.</em>
        </h1>
        <blockquote>“A wardrobe should become more itself with time.”</blockquote>
        <p>
          Black House began with a simple premise: the everyday layer deserves the same attention
          as the occasion piece. We cut small runs of outerwear — overcoats, trenches, field coats —
          in heavyweight cloth that ages rather than expires.
        </p>
        <p>
          Every piece is numbered by hand and finished with hardware that earns its patina. When a
          run ends, it ends; restocks are deliberate, never automatic.
        </p>
        <p>
          We sell direct: through this site, over WhatsApp, and from our studio in Bhopal,
          Madhya Pradesh. Bulk and uniform commissions are produced on the same lines,
          to the same standard.
        </p>
        <ul className="values">
          <li><strong>Small batches</strong><span>Limited runs, numbered by hand.</span></li>
          <li><strong>Durable cloth</strong><span>Heavyweight wool and cotton that age well.</span></li>
          <li><strong>Honest pricing</strong><span>GST-inclusive, no artificial markdown theatre.</span></li>
          <li><strong>Repair first</strong><span>Loose seam? We would rather fix it than replace it.</span></li>
        </ul>
      </Reveal>
    </main>
  );
}
