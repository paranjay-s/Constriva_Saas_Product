import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'accent' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  icon?: React.ReactNode;
  fullWidth?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  loading = false,
  leftIcon,
  rightIcon,
  icon,
  fullWidth = false,
  className = '',
  disabled,
  ...props
}) => {
  const effectiveLoading = isLoading || loading;
  const effectiveLeftIcon = leftIcon || icon;

  // the dashboard's look (features/dashboard/dashboard.css): pills, the cyan gradient, ink and hairlines
  const baseStyles =
    'inline-flex items-center justify-center font-medium transition-all duration-150 rounded-full cursor-pointer select-none disabled:opacity-55 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#bff6fb] focus-visible:ring-offset-2 focus-visible:ring-offset-[#04060a]';

  const sizeStyles = {
    sm: 'text-[13px] px-4 h-9 gap-1.5',
    md: 'text-sm px-5 h-11 gap-2',
    lg: 'text-[15px] px-6 h-12 gap-2.5',
  };

  const variantStyles = {
    // Primary and accent: the cyan gradient with ink text
    primary:
      'bg-[linear-gradient(135deg,#bff6fb,#7ca0ff)] text-[#04060a] hover:brightness-110 hover:-translate-y-px font-semibold tracking-tight',
    accent:
      'bg-[linear-gradient(135deg,#bff6fb,#7ca0ff)] text-[#04060a] hover:brightness-110 hover:-translate-y-px font-semibold tracking-tight',
    // Secondary: a translucent pill with a hairline border
    secondary:
      'bg-white/[0.06] border border-white/20 text-white hover:bg-white/[0.12]',
    // Ghost: text only until hovered
    ghost:
      'bg-transparent text-[#c9d3df] hover:text-white hover:bg-white/[0.08]',
    // Danger
    danger:
      'bg-[#ffb4ab]/10 border border-[#ffb4ab]/40 text-[#ffb4ab] hover:bg-[#ffb4ab]/20',
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${
        fullWidth ? 'w-full' : ''
      } ${className}`}
      disabled={disabled || effectiveLoading}
      {...props}
    >
      {effectiveLoading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        effectiveLeftIcon
      )}
      {children && <span>{children}</span>}
      {!effectiveLoading && rightIcon}
    </button>
  );
};
