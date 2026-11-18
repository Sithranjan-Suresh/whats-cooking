import { Shell } from "@/components/Shell";
import { Toaster } from "@/components/ui";
import { ThemeProvider } from "@/lib/theme";

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <Toaster>
        <Shell>{children}</Shell>
      </Toaster>
    </ThemeProvider>
  );
}
