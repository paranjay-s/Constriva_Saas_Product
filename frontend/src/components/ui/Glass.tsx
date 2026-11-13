import { forwardRef, useRef, type ElementType, type ComponentPropsWithoutRef, type ForwardedRef, type ReactNode, type ReactElement } from "react";
import { useGlass, type GlassOptions } from "../../hooks/useGlass";

type GlassProps<T extends ElementType = "div"> = {
  as?: T;
  children?: ReactNode;
  className?: string;
} & GlassOptions &
  ComponentPropsWithoutRef<T>;

export const Glass = forwardRef(function Glass<T extends ElementType = "div">(
  {
    as,
    children,
    className = "",
    refraction = 80,
    depth = 20,
    dispersion = 50,
    frost = 32,
    ...rest
  }: GlassProps<T>,
  forwardedRef: ForwardedRef<HTMLElement>
) {
  const innerRef = useRef<HTMLElement | null>(null);
  const Component = as || "div";

  useGlass(innerRef, { refraction, depth, dispersion, frost });

  const setRefs = (node: HTMLElement | null) => {
    innerRef.current = node;
    if (typeof forwardedRef === "function") {
      forwardedRef(node);
    } else if (forwardedRef) {
      forwardedRef.current = node;
    }
  };

  return (
    <Component
      ref={setRefs}
      className={className}
      data-glass
      data-glass-refraction={refraction}
      data-glass-depth={depth}
      data-glass-dispersion={dispersion}
      data-glass-frost={frost}
      {...rest}
    >
      {children}
    </Component>
  );
}) as <T extends ElementType = "div">(
  props: GlassProps<T> & { ref?: ForwardedRef<HTMLElement> }
) => ReactElement;
