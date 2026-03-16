import { useEffect } from "react";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `PigeonLab — ${title}`;
    return () => {
      document.title = "PigeonLab";
    };
  }, [title]);
}
