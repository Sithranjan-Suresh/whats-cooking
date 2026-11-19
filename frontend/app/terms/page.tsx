import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Terms of Service · What's Cooking?" };

export default function Terms() {
  return (
    <LegalPage title="Terms of Service" updated="November 19, 2026">
      <p>
        What&apos;s Cooking? is a free prototype provided as-is for testing. By using it you agree to these terms.
      </p>
      <h2>Your content</h2>
      <ul>
        <li>Only upload logos, photos and data you own or have permission to use.</li>
        <li>You&apos;re responsible for what you post to your YouTube channel. Review each video before posting.</li>
        <li>
          Posting uses YouTube API Services, so you also agree to the{" "}
          <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>.
        </li>
      </ul>
      <h2>AI-generated videos</h2>
      <p>
        Videos are generated with AI from your photo and the details you type. Captions and narration are limited to the dish
        name, price and description you provide, but always check a video before posting it.
      </p>
      <h2>Availability</h2>
      <p>
        The prototype runs on free hosting with a small shared budget for AI video. It may be slow, restart and clear stored
        files, switch to non-AI motion when the budget is used up, or be taken offline at any time.
      </p>
      <h2>No warranty</h2>
      <p>The service is provided without warranties of any kind, and we&apos;re not liable for any loss from using it.</p>
      <p>
        See also our <a href="/privacy">Privacy Policy</a>.
      </p>
    </LegalPage>
  );
}
