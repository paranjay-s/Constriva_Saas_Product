import { useEffect, type RefObject } from "react";

export function useMobileMenu(
  heroRef: RefObject<HTMLElement | null>,
  menuBtnRef: RefObject<HTMLButtonElement | null>,
  menuRef: RefObject<HTMLDivElement | null>
) {
  useEffect(() => {
    const hero = heroRef.current;
    const menuBtn = menuBtnRef.current;
    const menu = menuRef.current;

    if (!hero || !menuBtn || !menu) return;

    let timeoutId = 0;

    const setMenu = (open: boolean) => {
      menuBtn.setAttribute("aria-expanded", String(open));
      menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      hero.classList.toggle("is-menu-open", open);

      if (open) {
        clearTimeout(timeoutId);
        menu.hidden = false;
        requestAnimationFrame(() => {
          menu.classList.add("is-open");
        });
      } else {
        menu.classList.remove("is-open");
        clearTimeout(timeoutId);
        timeoutId = window.setTimeout(() => {
          if (menuBtn.getAttribute("aria-expanded") === "false") {
            menu.hidden = true;
          }
        }, 260);
      }
    };

    const handleClick = () => {
      const isOpen = menuBtn.getAttribute("aria-expanded") === "true";
      setMenu(!isOpen);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && menuBtn.getAttribute("aria-expanded") === "true") {
        setMenu(false);
        menuBtn.focus();
      }
    };

    const mediaQuery = window.matchMedia("(min-width: 901px)");
    const handleMediaChange = (e: MediaQueryListEvent) => {
      if (e.matches) setMenu(false);
    };

    menuBtn.addEventListener("click", handleClick);
    document.addEventListener("keydown", handleKeyDown);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleMediaChange);
    } else {
      mediaQuery.addListener(handleMediaChange);
    }

    return () => {
      clearTimeout(timeoutId);
      menuBtn.removeEventListener("click", handleClick);
      document.removeEventListener("keydown", handleKeyDown);
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleMediaChange);
      } else {
        mediaQuery.removeListener(handleMediaChange);
      }
    };
  }, [heroRef, menuBtnRef, menuRef]);
}

