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
        These are stored on our server only to make your videos. The prototype runs on free hosting that clears its storage
        whenever it restarts, so uploads and generated videos are deleted then. Everyone using this test site shares one
        demo workspace, so don&apos;t upload anything you wouldn&apos;t want other testers to see.
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
        Your YouTube access token is encrypted and stored <b>only in your own browser</b>. Our server doesn&apos;t keep it, and we never
        share, sell or use your Google data for anything else. You can disconnect in the app at any time, and revoke access
        entirely at <a href="https://myaccount.google.com/permissions">myaccount.google.com/permissions</a>.
      </p>
      <p>
        What&apos;s Cooking?&apos;s use and transfer of information received from Google APIs adheres to the{" "}
        <a href="https://developers.google.com/terms/api-services-user-data-policy">Google API Services User Data Policy</a>, including the
        Limited Use requirements. This app uses YouTube API Services; see the{" "}
        <a href="https://policies.google.com/privacy">Google Privacy Policy</a>.
      </p>

      <h2>Cookies and tracking</h2>
      <p>No analytics, ads or tracking cookies. Your browser&apos;s local storage holds your YouTube connection and a sound on/off setting.</p>

      <h2>Contact</h2>
      <p>
        Questions or deletion requests: open an issue at <a href={REPO}>{REPO.replace("https://", "")}</a>.
      </p>
    </LegalPage>
  );
}
