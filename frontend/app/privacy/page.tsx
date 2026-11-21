import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Privacy Policy · What's Cooking?" };

const REPO = "https://github.com/Sithranjan-Suresh/whats-cooking";

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="November 19, 2026">
      <p>
        What&apos;s Cooking? is a prototype that turns a restaurant&apos;s dish photo or sales export into a short video and, if
        you choose, posts it to your YouTube channel. This page explains what it does with your data.
      </p>

      <h2>What you give us</h2>
      <ul>
        <li>The logo, restaurant name, dish photos, dish names, prices and descriptions you upload or type.</li>
        <li>Sales CSV files you upload (item names, dates, quantities, revenue).</li>
      </ul>
      <p>
        There are no accounts. The first time you open the site, your browser creates a random studio id and keeps it in its
        local storage; everything you add is filed under that id. Your name, logo, photos, dish details, sales data and video
        history are stored in our database (Neon Postgres) so they survive server restarts, and so are the videos we make for
        you (older ones are cleared when storage fills up; anything you posted stays on YouTube). If you sign in with
        Google, we also store your name, email and profile picture to keep your studio on every device.
      </p>
      <p>
        The studio id isn&apos;t a password: this is a prototype, so don&apos;t upload anything confidential. To have a studio
        deleted, contact us (below) from that browser and we&apos;ll remove it.
      </p>

      <h2>Where it runs</h2>
      <p>
        The website is hosted on Vercel, the video server on Render, and the database on Neon. They process data only to run
        the service.
      </p>

      <h2>AI processing</h2>
      <p>
        To write the script and animate the dish, your photo, dish details and sales summaries are sent to Google&apos;s Gemini API.
        The narrator voice is generated with Microsoft&apos;s text-to-speech service. We don&apos;t send your YouTube data to these
        services.
      </p>

      <h2>YouTube</h2>
      <p>If you connect YouTube, you sign in with Google and grant two permissions:</p>
      <ul>
        <li><b>Upload videos</b> (youtube.upload): used only when you press Post to YouTube, to upload that video to your channel.</li>
        <li>
          <b>View your YouTube account</b> (youtube.readonly): used to show your channel&apos;s name and to list the videos you
          posted with this app.
        </li>
      </ul>
      <p>
        Your YouTube access token is always encrypted. If you use the app without signing in, it&apos;s stored <b>only in your
        own browser</b>. If you&apos;re signed in, it&apos;s saved (encrypted) to your account on our server so it works on all your
        devices. We never share, sell or use your Google data for anything else. <b>Disconnect</b> in the app revokes the access
        at Google and deletes it from our server; you can also revoke it any time at{" "}
        <a href="https://myaccount.google.com/permissions">myaccount.google.com/permissions</a>.
      </p>
      <p>
        What&apos;s Cooking?&apos;s use and transfer of information received from Google APIs adheres to the{" "}
        <a href="https://developers.google.com/terms/api-services-user-data-policy">Google API Services User Data Policy</a>, including the
        Limited Use requirements. This app uses YouTube API Services; see the{" "}
        <a href="https://policies.google.com/privacy">Google Privacy Policy</a>.
      </p>

      <h2>Cookies and tracking</h2>
      <p>No analytics, ads or tracking cookies. Your browser&apos;s local storage holds your studio id, your sign-in session, your YouTube connection if you aren&apos;t signed in, and a sound on/off setting.</p>

      <h2>Contact</h2>
      <p>
        Questions or deletion requests: open an issue at <a href={REPO}>{REPO.replace("https://", "")}</a>.
      </p>
    </LegalPage>
  );
}
