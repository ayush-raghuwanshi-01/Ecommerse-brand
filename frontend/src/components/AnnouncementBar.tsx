import { Fragment } from 'react';

/**
 * Continuous-scroll offer strip (Uptownie/Myntra pattern) — the "reason to
 * act now" band that is always on screen. One offer + code, one trust
 * promise, one cadence promise, repeated so the loop is seamless.
 */
const ITEMS = [
  'Free shipping on orders above ₹15,000',
  '₹500 off your first order · code WELCOME500',
  '7-day easy returns',
  'COD & UPI available',
  'New numbered drops twice a year',
];

function Row() {
  return (
    <>
      {ITEMS.map((t) => (
        <Fragment key={t}>
          <span>{t}</span>
          <i className="dot" aria-hidden="true">
            ❀
          </i>
        </Fragment>
      ))}
    </>
  );
}

export default function AnnouncementBar() {
  return (
    <div className="announce" role="status" aria-live="off">
      <div className="announce-track">
        <div className="announce-row">
          <Row />
          <Row />
        </div>
      </div>
    </div>
  );
}
