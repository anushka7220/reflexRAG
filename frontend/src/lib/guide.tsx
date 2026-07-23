import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

/* Lets any component steer Inkling.

   Two layers, deliberately:

   - BASE is the ambient guidance, set by App from app state (searching,
     ingesting, chatting). It is always present, so Inkling always has
     something to say rather than going silent.
   - FOCUS is a temporary override set by direct interaction: typing in the
     repo field, hovering a repo card. It wins while it lasts, and clearing
     it drops straight back to base.

   Splitting them this way means a hover never has to know what to restore
   afterwards, which is what makes the "always guiding" behaviour hold
   together as more components start steering him. */

export type GuideMood = "idle" | "curious" | "working" | "happy";

export interface GuideAim {
  target: string | null;
  say?: string;
  mood?: GuideMood;
}

interface GuideApi {
  aim: GuideAim;
  setBase: (a: GuideAim) => void;
  focus: (a: GuideAim) => void;
  blur: () => void;
}

const Ctx = createContext<GuideApi | null>(null);

export function GuideProvider({ children }: { children: ReactNode }) {
  const [base, setBaseRaw] = useState<GuideAim>({ target: null });
  const [focused, setFocused] = useState<GuideAim | null>(null);

  // Changing the ambient aim means the app moved on (a repo was picked, a
  // screen changed). Any hover override still hanging around belongs to a
  // component that has since unmounted and can never call blur(), so we
  // clear it here rather than let a stale bubble follow the user around.
  const setBase = useCallback((a: GuideAim) => {
    setBaseRaw(a);
    setFocused(null);
  }, []);

  const focus = useCallback((a: GuideAim) => setFocused(a), []);
  const blur = useCallback(() => setFocused(null), []);

  const value = useMemo<GuideApi>(
    () => ({ aim: focused ?? base, setBase, focus, blur }),
    [focused, base, focus, blur]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useGuide(): GuideApi {
  const ctx = useContext(Ctx);
  if (!ctx) {
    // Safe no-op so components using the hook never crash outside a provider.
    return {
      aim: { target: null },
      setBase: () => {},
      focus: () => {},
      blur: () => {},
    };
  }
  return ctx;
}