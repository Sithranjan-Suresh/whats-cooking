import { Shell } from "@/components/Shell";
import { Toaster } from "@/components/ui";

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <Toaster>
      <Shell>{children}</Shell>
    </Toaster>
  );
}
